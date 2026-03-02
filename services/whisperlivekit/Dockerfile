# ─────────────────────────────────────────────────────────────────────────────
# WhisperLiveKit STT Server
#
# Builds from the manual setup steps documented in README.md:
#   uv pip install whisperlivekit pyaudio
#   wlk --model <size> --host 0.0.0.0 --port 8000 --pcm-input --language es
#
# Python is managed entirely by uv (no system Python needed from apt).
# GPU: NVIDIA CUDA required for Whisper inference.
# Base image: Ubuntu 24.04 (matches the LD_LIBRARY_PATH for ONNX noted in
# the original server_dockerization/docker-compose.yaml).
#
# Runtime tunables (env vars, no rebuild needed):
#   WHISPER_MODEL   — tiny | base | small | medium | large (default: medium)
#   WHISPER_LANG    — language code passed to --language (default: es)
#   HF_HOME         — HuggingFace cache dir (default: /app/hf_cache)
# ─────────────────────────────────────────────────────────────────────────────

# TODO: Review CUDA version — 12.6.3 targets the current EC2 baseline.
#       If the instance has a different driver, adjust the tag accordingly.
FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/hf_cache

# Runtime defaults — override via env vars at docker run / compose time
ENV WHISPER_MODEL=medium
ENV WHISPER_LANG=es

# Only non-Python system deps:
#   portaudio19-dev  — C headers needed to compile pyaudio
#   ffmpeg           — audio decoding used by whisperlivekit
#   build-essential  — gcc/make needed to compile C extensions (pyaudio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    ffmpeg \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv — manages both the Python interpreter and packages
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

# Install Python 3.12 via uv and create an isolated venv
RUN uv python install 3.12 \
    && uv venv --python 3.12 /opt/whisper-venv \
    && uv pip install --python /opt/whisper-venv/bin/python \
        whisperlivekit pyaudio

# Put the venv on PATH so the `wlk` CLI entry-point is found at runtime
ENV PATH="/opt/whisper-venv/bin:$PATH"

# ONNX runtime library path — required on Ubuntu 24.04.
# Points to /opt/whisper-venv where onnxruntime is installed as a transitive
# dependency of whisperlivekit (not the old /opt/venv placeholder).
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/opt/whisper-venv/lib/python3.12/site-packages/onnxruntime/capturable_lib

WORKDIR /app

# /app/hf_cache is expected to be bind-mounted from the host so that model
# weights survive container restarts and are not re-downloaded on each start.
# On EC2, point the host-side path at the partition dedicated to large files
# (set in docker-compose.yml or docker run -v <partition-path>:/app/hf_cache).
RUN mkdir -p /app/hf_cache

EXPOSE 8000

# --pcm-input is required by the Pipecat WhisperLiveKitSTT integration
# (the plugin streams raw 16kHz PCM over the WebSocket, not encoded audio)
CMD wlk \
    --model "${WHISPER_MODEL}" \
    --host 0.0.0.0 \
    --port 8000 \
    --pcm-input \
    --language "${WHISPER_LANG}"
