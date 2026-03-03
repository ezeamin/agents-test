# ─────────────────────────────────────────────────────────────────────────────
# Chatterbox TTS Server — Multilingual build
#
# Builds from the multilingual setup steps documented in README.md.
#
# WHY TWO REPOS:
#   - devnen/Chatterbox-TTS-Server  → provides working requirements (nvidia)
#   - 4-alok/Chatterbox-TTS-Server  → provides multilingual server code (Spanish)
#
# The 4-alok fork's own requirements are outdated / broken, so we install
# dependencies from devnen and run the 4-alok server against that environment.
# This matches the manual steps in README.md exactly.
#
# Python 3.10 is required — Chatterbox has dependency conflicts with 3.12.
#
# GPU: NVIDIA CUDA required for TTS inference.
#
# Volumes expected at runtime:
#   /app/cache  — unified cache dir (bind-mount to the appropriate EC2 partition).
#                 /root/.cache is symlinked here so ALL libraries that write to
#                 ~/.cache (HuggingFace, torch, pip, etc.) end up in this volume.
#
# Runtime tunables (env vars):
#   HF_HOME         — HuggingFace cache dir (default: /app/cache/huggingface)
#   XDG_CACHE_HOME  — catch-all for XDG-compliant caches (default: /app/cache)
# ─────────────────────────────────────────────────────────────────────────────

# Ubuntu 22.04 matches the official Chatterbox server Dockerfile and is the
# platform for which the resemble-perth wheels are built. Using 24.04 caused
# perth's C extension to load as NoneType silently, crashing ChatterboxMultilingualTTS.
# TODO: Review CUDA version — 12.6.3 targets the current EC2 baseline.
#       If the instance has a different driver, adjust the tag accordingly.
FROM nvidia/cuda:12.6.3-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Unified cache volume — all libraries that write to ~/.cache are redirected here
# via the /root/.cache symlink created below.
ENV HF_HOME=/app/cache/huggingface
ENV XDG_CACHE_HOME=/app/cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    build-essential \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv — it manages the Python 3.10 interpreter download as well
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

# Download Python 3.10 via uv (mirrors the manual `uv venv --python 3.10` step)
RUN uv python install 3.10

# Create the unified cache dir and symlink /root/.cache to it.
# At runtime the bind-mount replaces /app/cache with the host partition, so
# everything written to ~/.cache at runtime lands in the mounted volume.
RUN mkdir -p /app/cache && ln -sfn /app/cache /root/.cache

WORKDIR /build

# ── Step 1: Clone devnen repo and install its dependencies ───────────────────
# We use devnen's requirements-nvidia.txt as the authoritative dependency set.
# The venv is created explicitly so that the 4-alok server can reuse it.
RUN git clone https://github.com/devnen/Chatterbox-TTS-Server.git devnen

# Install devnen's deps first (provides torch for the correct CUDA version and
# all server utilities). Then upgrade chatterbox-tts to the ResembleAI git master —
# this is the same source used in the official Chatterbox Dockerfile's requirements.
# The git version declares resemble-perth as a proper dependency so uv resolves the
# compatible version automatically, rather than us installing it in isolation (which
# installs the package but leaves its C extension silently broken).
RUN uv venv --python 3.10 /opt/chatterbox-venv \
    && uv pip install --python /opt/chatterbox-venv/bin/python \
        --upgrade pip setuptools wheel \
    && uv pip install --python /opt/chatterbox-venv/bin/python \
        -r devnen/requirements-nvidia.txt \
    && uv pip install --python /opt/chatterbox-venv/bin/python \
        "chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@master"

# ── Step 2: Clone the multilingual server code (4-alok fork) ─────────────────
# TODO: The 4-alok fork was originally developed on macOS and may contain
#       Mac-specific path assumptions or platform checks. Review before
#       promoting to production — known areas to check:
#         - Any `platform.system() == "Darwin"` branches
#         - Hardcoded paths like ~/Library or /Users/
#         - Audio backend selection (sounddevice, pyaudio device indices)
RUN git clone https://github.com/4-alok/Chatterbox-TTS-Server.git multilingual

# ── Step 3: Apply our config overrides ───────────────────────────────────────
# The 4-alok fork's config.yaml contains Mac-specific defaults and path
# assumptions that break on Linux. We ship a patched version of config.yaml
# alongside this Dockerfile (in services/chatterbox/) that fixes those issues
# and routes storage paths to the bind-mounted cache volume (/app/cache/*).
# This avoids maintaining a separate fork just for a config change.
COPY config.yaml /build/multilingual/config.yaml

WORKDIR /build/multilingual

EXPOSE 8004

# Run 4-alok's server.py using the venv built from devnen's requirements.
# We exec directly into the venv Python to avoid needing uv in the PATH at runtime.
CMD ["/opt/chatterbox-venv/bin/python", "server.py"]
