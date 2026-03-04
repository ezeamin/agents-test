# Project Overview

This repository implements **Nova**, a voice-based conversational AI agent built on the [Pipecat](https://github.com/pipecat-ai/pipecat) framework. Nova acts as a sports specialist for "Strata Sportiva," capable of handling product searches, shopping cart management, order tracking, and customer service — all through natural voice interaction in Spanish.

The agent supports swappable backends for each stage of the voice pipeline (STT, LLM, TTS) via environment variables, and can be run locally or deployed as a Docker container. Transport is handled via WebRTC, Daily, or Twilio/WebSocket depending on the deployment scenario.

Key design decisions:
- All service providers (STT, TTS) are selected at startup via `.env` variables — no code changes required to switch providers.
- The STT (WhisperLiveKit) and TTS (Chatterbox) servers are containerized in `services/` and managed via docker-compose alongside the agent. They can also be run manually on the same or a separate instance.
- The LLM is always AWS Bedrock (Claude Haiku 4.5).
- Smart turn detection uses Pipecat's `LocalSmartTurnAnalyzerV3` with Silero VAD to determine when the user has finished speaking.

---

# Repository Schema

```
.
├── Dockerfile                          # Container image for the main agent
├── docker-compose.yml                  # Compose file: nova-agent + stt-whisper + tts-chatterbox (+ optional Piper)
├── requirements.txt                    # Python dependencies (pipecat extras, boto3, etc.)
├── .env.example                        # Template for all required environment variables
│
├── cdk/                                # AWS CDK TypeScript project (infrastructure as code)
│   ├── bin/app.ts                      # CDK app entry point — instantiates stacks
│   ├── lib/ecr-stack.ts                # EcrStack: 3 ECR repos (nova-agent, stt-whisper, tts-chatterbox)
│   ├── package.json
│   ├── tsconfig.json
│   └── cdk.json
│
├── .github/
│   └── workflows/
│       └── build-push-ecr.yml         # CI/CD: builds all 3 images and pushes to ECR on push to master
│
├── src/
│   ├── agent.py                        # Entry point: FastAPI server, WebRTC routes, debug WS
│   ├── frontend/
│   │   └── index.html                  # Debug browser client (WebRTC + mic mute + STT/LLM display)
│   ├── pipelines/
│   │   ├── __init__.py                 # Re-exports run_bot and _debug
│   │   └── nova.py                     # Pipeline: DebugBroadcaster, DebugFrameCapture, run_bot
│   └── helpers/
│       ├── __init__.py                 # Re-exports all helpers for clean imports in agent.py
│       ├── config.py                   # ICE_SERVERS list and SYSTEM_MESSAGE
│       ├── services.py                 # Factory functions: create_stt_service, create_tts_service, create_llm_service
│       ├── tools.py                    # LLM tool definitions (functions + schema) for mock e-commerce actions
│       ├── chatterbox_custom_integration.py      # Custom Pipecat TTSService for the Chatterbox server API
│       └── whisper_livekit_custom_integration.py # Custom Pipecat STTService for WhisperLiveKit WebSocket API
│
├── services/
│   ├── chatterbox/
│   │   ├── Dockerfile                  # Container image for Chatterbox TTS (clones devnen/Chatterbox-TTS-Server)
│   │   ├── config.yaml                 # Patched config: Linux/Docker paths, GPU device, Spanish language defaults
│   │   └── prev.Dockerfile             # Previous two-repo multilingual build (kept for reference)
│   └── whisperlivekit/
│       └── Dockerfile                  # Container image for WhisperLiveKit STT server
│
├── scripts/
│   ├── whisperlivekit_websocket.py     # Standalone test script: streams mic audio to the WhisperLiveKit server
│   ├── pipecat-examples-webrtc-docker/ # Reference example from Pipecat docs (custom server+client pattern)
│   └── piper/
│       ├── Dockerfile                  # Container image for the Piper TTS HTTP server
│       └── run_piper.py               # Entrypoint for the Piper TTS server (wraps piper.http_server)
│
└── voice/                              # Directory for Piper voice model files (.onnx + config)
```

---

# Architecture

The server is a custom **FastAPI** app (not the Pipecat runner). It creates a `SmallWebRTCRequestHandler` with ICE servers at startup, handles the WebRTC offer/answer exchange, and spawns an independent pipeline task per client. A `/ws/debug` WebSocket endpoint broadcasts STT, LLM, and TTS events to the debug frontend in real time.

The pipeline follows a linear audio processing chain:

```
User (Browser)
        │  audio in
        ▼
   SmallWebRTCTransport  (ICE via STUN/TURN — see ICE Servers section)
        │
        ▼
   STT Service  ──────────────────────────────────────────────────────────────────┐
   (WhisperLiveKit WS | Whisper local | Deepgram)                                 │
        │  TranscriptionFrame                                                      │
        ▼                                                                          │
   [DebugFrameCapture]  → /ws/debug (STT events)                                  │
        │                                                                          │
        ▼                                                                          │
   User Context Aggregator  (smart turn detection via LocalSmartTurnAnalyzerV3)   │
        │  complete user turn                                                      │
        ▼                                                                          │
   LLM Service  (AWS Bedrock — Claude Haiku 4.5)                                  │
        │  TextFrame / tool calls                                                  │
        ▼                                                                          │
   [DebugFrameCapture]  → /ws/debug (LLM text events)                             │
        │                                                                          │
        ▼                                                                          │
   TTS Service  ──────────────────────────────────────────────────────────────────┘
   (Chatterbox Server | Piper | AWS Polly | ElevenLabs)
        │  audio out
        ▼
   [DebugFrameCapture]  → /ws/debug (TTS start/stop events)
        │
        ▼
   SmallWebRTCTransport output  →  User
```

### Services

| Stage | Provider | Notes |
|-------|----------|-------|
| **STT** | `WHISPER_STREAM` (default) | Streams 16kHz PCM over WebSocket to a remote WhisperLiveKit server |
| | `WHISPER` | Runs Whisper locally on CPU (slow, no external server needed) |
| | `DEEPGRAM` | Cloud API; requires `DEEPGRAM_API_KEY` |
| **LLM** | AWS Bedrock | Always used; model `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| **TTS** | `CHATTERBOX_SERVER` (default) | Streams WAV chunks from a remote Chatterbox server's `/tts` endpoint |
| | `CHATTERBOX_SERVER_OPENAI` | Same server, OpenAI-compatible `/v1/audio/speech` endpoint |
| | `PIPER` | Self-hosted Piper TTS (can be run via `scripts/piper/`); requires voice `.onnx` files in `voice/` |
| | `POLLY` | AWS Polly generative voice (`Lupe`, `es-US`) |
| | `ELEVENLABS` | Requires `ELEVENLABS_API_KEY` |

### Transport

The only active transport is **WebRTC via `SmallWebRTCTransport`**. The agent runs with `network_mode: host` in Docker so that `aiortc` binds directly to the host network interfaces — this is required for STUN to discover and advertise the correct public IP on EC2. With bridge networking, `aiortc` would bind to random ephemeral ports that Docker's port mapping doesn't cover.

The signaling flow:
- `POST /api/offer` — browser sends SDP offer, server returns SDP answer
- `PATCH /api/offer` — trickle ICE candidate exchange
- `GET /` — serves the debug frontend (`src/frontend/index.html`)
- `GET /ws/debug` — WebSocket stream of STT/LLM/TTS debug events

### ICE Servers

ICE servers are configured in two places that **must both be set**:
1. **Server-side** — `SmallWebRTCRequestHandler(ice_servers=[IceServer(urls=ICE_SERVERS)])` in `agent.py`. Controls what STUN/TURN the Pipecat server uses to discover its own public IP candidate.
2. **Client-side** — `new RTCPeerConnection({ iceServers: [...] })` in `src/frontend/index.html`. Controls what STUN/TURN the browser uses.

The `ICE_SERVERS` list is read from the `ICE_SERVERS` environment variable (comma-separated URLs), defaulting to two Google STUN servers.

> **⚠️ Development only:** The current Google STUN configuration is sufficient for testing but not reliable for production. STUN only works when the network allows direct UDP. Symmetric NAT, firewalls, or enterprise networks will cause ICE to fail. **Production should use a TURN server**, which relays media through a known public endpoint regardless of NAT type.
>
> Managed TURN providers compatible with the `ICE_SERVERS` env var format (pass credentials as `turn:host?transport=udp` with `username`/`credential` in the URL or a separate `IceServer` object):
> - **Twilio** — Network Traversal Service (NTS). Pipecat also has a native Twilio transport for telephony.
> - **Daily** — Provides managed TURN. Pipecat also has a native Daily transport.
> - **Telnyx** — Provides managed TURN. Pipecat also has a native Telnyx transport.
> - **Metered.ca** — Free tier available, good for testing.
> - **Cloudflare TURN** — In beta, generous free tier.
> - **Coturn** — Self-hosted option, can run as a sidecar on the same EC2 instance.

### Tools (LLM Function Calling)

The agent registers mock e-commerce tools in [src/helpers/tools.py](src/helpers/tools.py) that the LLM can call to handle user requests:

| Tool | Description |
|------|-------------|
| `identify_user` | Look up a user by ID / document number |
| `search_products` | Filter product catalog by category or max price |
| `check_for_size` | Verify size availability for a product |
| `add_to_cart` | Add a product to the shopping cart |
| `apply_promo` | Apply a promotional discount or trial period |
| `order_cart` | Confirm and place the cart order |
| `get_order_status` | Query the status of an existing order |
| `final_survey` | Record end-of-call satisfaction survey |

### Environment Variables

All configuration is done via `.env` (see `.env.example`):

- `STT_SERVICE_PROVIDER` — Select STT backend (`WHISPER_STREAM`, `WHISPER`, `DEEPGRAM`)
- `TTS_SERVICE_PROVIDER` — Select TTS backend (`CHATTERBOX_SERVER`, `CHATTERBOX_SERVER_OPENAI`, `PIPER`, `POLLY`, `ELEVENLABS`)
- `EC2_HOST` — Fallback hostname for external STT/TTS servers
- `EC2_HOST_WHISPER_STREAM`, `EC2_HOST_CHATTERBOX`, `EC2_HOST_PIPER` — Per-service host overrides
- `EC2_WHISPER_PORT`, `EC2_CHATTERBOX_PORT`, `EC2_PIPER_PORT` — Server ports (defaults: 8000, 8004, 5002)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION` — For Bedrock LLM and Polly TTS
- `DEEPGRAM_API_KEY` — Required if using Deepgram STT
- `ELEVENLABS_API_KEY` — Required if using ElevenLabs TTS
- `CURRENT_VOICE`, `CURRENT_VOICE_CONFIG` — Piper voice model filename and config (for Piper TTS)

### Running the Agent

**Local (Python 3.12+, with `uv`):**
```bash
uv pip install -r requirements.txt
cp .env.example .env  # fill in credentials
uv run src/agent.py   # serves on http://localhost:7860
```

**Docker (EC2 — uses `network_mode: host` for nova-agent):**
```bash
# Full stack (agent + local GPU STT + local GPU TTS):
docker compose --profile gpu-all up --build

# Agent only (when using cloud STT/TTS APIs like Deepgram / Polly / ElevenLabs):
docker compose up --build

# Individual GPU services:
docker compose --profile gpu-stt up --build   # agent + stt-whisper only
docker compose --profile gpu-tts up --build   # agent + tts-chatterbox only

# Pull pre-built images from ECR instead of building locally:
# Set NOVA_AGENT_IMAGE, STT_WHISPER_IMAGE, TTS_CHATTERBOX_IMAGE in .env to the ECR URIs,
# then run without --build:
docker compose --profile gpu-all pull
docker compose --profile gpu-all up
```
Set `EC2_HOST=localhost` in `.env` — all services communicate via the host loopback.

**Test STT connection standalone:**
```bash
python scripts/whisperlivekit_websocket.py
```

# State Of Things

## Current Status

All three services (nova-agent, stt-whisper, tts-chatterbox) are containerized and managed together via docker-compose. The stack is deployed on an EC2 instance exposed publicly via HTTPS using Load Balancers and Target Groups.

Docker Compose profiles (`gpu-stt`, `gpu-tts`, `gpu-all`) allow selectively running the GPU services; when using cloud STT/TTS APIs the heavy containers can be skipped entirely.

ECR repositories for all three images are provisioned via CDK (`cdk/`). A GitHub Actions workflow (`.github/workflows/build-push-ecr.yml`) builds and pushes all images to ECR on every push to `master`.

## Pending Tasks

Those tagged with \[OTHERS\] will be implemented by other people in the team. The untagged ones can be tackled whenever there is time.

A. \[DONE\] Dockerfiles and docker-compose integration for STT and TTS servers (`services/`).

B. \[DONE\] ECR repositories created via CDK (`cdk/lib/ecr-stack.ts`). GitHub Actions CI/CD pipeline pushes images on every merge to master.

C. Deployment infra CDK stack: EC2 instance (or ECS with EC2 launch type for GPU support), Load Balancer, Target Groups, and HTTPS certificate attachment. See `TODO.md` for a full trade-off table of deployment options. GCP equivalents pending.

D. \[OTHERS\] Replace the debug web UI with custom applications or integrations with other communication services (telephony, etc.).