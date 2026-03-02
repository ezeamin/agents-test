# ─────────────────────────────────────────────────────────────────────────────
# WhisperLiveKit STT Server
#
# Builds from the manual setup steps documented in README.md:
#   apt install ffmpeg portaudio19-dev python3-dev
#   uv pip install whisperlivekit pyaudio
#   wlk --model <size> --host 0.0.0.0 --port 8000 --pcm-input --language es
#
# GPU: NVIDIA CUDA required for Whisper inference.
# Base image targets Ubuntu 24.04 to match the LD_LIBRARY_PATH for ONNX
# noted in the original server_dockerization/docker-compose.yaml.
#
# Runtime tunables (env vars, no rebuild needed):
#   WHISPER_MODEL   — tiny | base | small | medium | large (default: medium)
#   WHISPER_LANG    — language code passed to --language (default: es)
#   HF_HOME         — HuggingFace cache dir (default: /app/hf_cache)
# ─────────────────────────────────────────────────────────────────────────────

FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/hf_cache

# ONNX runtime library path — required on Ubuntu 24.04 (see server_dockerization compose)
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/opt/venv/lib/python3.12/site-packages/onnxruntime/capturable_lib

# Runtime defaults — override via env vars at docker run / compose time
ENV WHISPER_MODEL=medium
ENV WHISPER_LANG=es

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    ffmpeg \
    portaudio19-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

RUN uv pip install --system whisperlivekit pyaudio

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
