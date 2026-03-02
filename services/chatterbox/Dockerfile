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
#   /app/hf_cache   — HuggingFace model cache (bind-mount to persist downloads)
#   /app/voices     — Voice reference audio files (.wav) for cloning / predefined
#   /app/outputs    — Server output directory
#
# On EC2, point each host-side bind-mount at the partition dedicated to that
# type of data (large model files → storage partition, outputs → scratch, etc.).
# See docker-compose.yml for the mount configuration.
#
# Runtime tunables (env vars):
#   HF_HOME         — HuggingFace cache dir (default: /app/hf_cache)
# ─────────────────────────────────────────────────────────────────────────────

# Ubuntu 24.04 — Python 3.10 is managed by uv (not apt) to match the manual
# setup steps in README.md and keep both containers on the same Ubuntu base.
# uv downloads the Python 3.10 interpreter directly, no PPA or base-image
# change needed.
# TODO: Review CUDA version — 12.6.3 targets the current EC2 baseline.
#       If the instance has a different driver, adjust the tag accordingly.
FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/hf_cache

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

WORKDIR /build

# ── Step 1: Clone devnen repo and install its dependencies ───────────────────
# We use devnen's requirements-nvidia.txt as the authoritative dependency set.
# The venv is created explicitly so that the 4-alok server can reuse it.
RUN git clone https://github.com/devnen/Chatterbox-TTS-Server.git devnen

RUN uv venv --python 3.10 /opt/chatterbox-venv \
    && uv pip install --python /opt/chatterbox-venv/bin/python \
        --upgrade pip setuptools wheel \
    && uv pip install --python /opt/chatterbox-venv/bin/python \
        -r devnen/requirements-nvidia.txt

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
# and routes all storage paths to the bind-mounted volumes (/app/*).
# This avoids maintaining a separate fork just for a config change.
COPY config.yaml /build/multilingual/config.yaml

WORKDIR /build/multilingual

RUN mkdir -p /app/hf_cache /app/voices /app/outputs

# Symlink the runtime directories into the server's expected relative locations.
# These are a fallback for any code paths that reference ./voices or ./outputs
# relative to the working directory rather than reading from config.yaml.
# If config.yaml already points to /app/* directly, these are harmless.
RUN ln -sfn /app/voices /build/multilingual/voices \
    && ln -sfn /app/outputs /build/multilingual/outputs

EXPOSE 8004

# Run 4-alok's server.py using the venv built from devnen's requirements.
# We exec directly into the venv Python to avoid needing uv in the PATH at runtime.
CMD ["/opt/chatterbox-venv/bin/python", "server.py"]
