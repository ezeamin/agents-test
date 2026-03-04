# ── Stage 1: build React frontend ────────────────────────────────────────────
FROM oven/bun:latest AS frontend-builder

# Build-time variables for Vite (VITE_* vars are baked into the bundle)
# Pass them via: docker build --build-arg VITE_COGNITO_DOMAIN=https://...
ARG VITE_COGNITO_DOMAIN
ARG VITE_COGNITO_CLIENT_ID
ARG VITE_COGNITO_REDIRECT_URI
ARG VITE_COGNITO_LOGOUT_URI
ARG VITE_ICE_SERVERS

ENV VITE_COGNITO_DOMAIN=$VITE_COGNITO_DOMAIN
ENV VITE_COGNITO_CLIENT_ID=$VITE_COGNITO_CLIENT_ID
ENV VITE_COGNITO_REDIRECT_URI=$VITE_COGNITO_REDIRECT_URI
ENV VITE_COGNITO_LOGOUT_URI=$VITE_COGNITO_LOGOUT_URI
ENV VITE_ICE_SERVERS=$VITE_ICE_SERVERS

WORKDIR /build

# Install dependencies first (cache-friendly layer)
COPY src/frontend/package.json src/frontend/bun.lock* ./
RUN bun install --frozen-lockfile

# Copy source and build
COPY src/frontend/ ./
RUN bun run build

# ── Stage 2: Python agent ─────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    libsndfile1 \
    curl \
    ca-certificates \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY src/ src/

# Copy the compiled frontend into the image
COPY --from=frontend-builder /build/dist/ src/frontend/dist/

EXPOSE 7860

CMD ["uv", "run", "src/agent.py", "--host", "0.0.0.0"]
