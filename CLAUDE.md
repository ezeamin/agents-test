# Project Overview

This repository implements **Nova**, a voice-based conversational AI agent built on the [Pipecat](https://github.com/pipecat-ai/pipecat) framework. Nova acts as a sports specialist for "Strata Sportiva," capable of handling product searches, shopping cart management, order tracking, and customer service — all through natural voice interaction in Spanish.

The agent supports swappable backends for each stage of the voice pipeline (STT, LLM, TTS) via environment variables, and can be run locally or deployed as a Docker container. Transport is handled via WebRTC, Daily, or Twilio/WebSocket depending on the deployment scenario.

Key design decisions:
- All service providers (STT, TTS) are selected at startup via `.env` variables — no code changes required to switch providers.
- External STT and TTS servers (WhisperLiveKit, Chatterbox) are expected to be running separately, typically on an EC2 instance.
- The LLM is always AWS Bedrock (Claude Haiku 4.5).
- Smart turn detection uses Pipecat's `LocalSmartTurnAnalyzerV3` with Silero VAD to determine when the user has finished speaking.

---

# Repository Schema

```
.
├── Dockerfile                          # Container image for the main agent
├── docker-compose.yml                  # Compose file: agent + optional Piper TTS service
├── requirements.txt                    # Python dependencies (pipecat extras, boto3, etc.)
├── .env.example                        # Template for all required environment variables
│
├── src/
│   ├── agent.py                        # Entry point: builds and runs the Pipecat pipeline
│   └── helpers/
│       ├── __init__.py                 # Re-exports all helpers for clean imports in agent.py
│       ├── config.py                   # Transport params (Daily/WebRTC/Twilio) and SYSTEM_MESSAGE
│       ├── services.py                 # Factory functions: create_stt_service, create_tts_service, create_llm_service
│       ├── tools.py                    # LLM tool definitions (functions + schema) for mock e-commerce actions
│       ├── chatterbox_custom_integration.py      # Custom Pipecat TTSService for the Chatterbox server API
│       └── whisper_livekit_custom_integration.py # Custom Pipecat STTService for WhisperLiveKit WebSocket API
│
├── scripts/
│   ├── whisperlivekit_websocket.py     # Standalone test script: streams mic audio to the WhisperLiveKit server
│   └── piper/
│       ├── Dockerfile                  # Container image for the Piper TTS HTTP server
│       └── run_piper.py               # Entrypoint for the Piper TTS server (wraps piper.http_server)
│
└── voice/                              # Directory for Piper voice model files (.onnx + config)
```

---

# Architecture

The pipeline follows a linear audio processing chain:

```
User (Browser / Phone)
        │  audio in
        ▼
   Transport (WebRTC / Daily / Twilio)
        │
        ▼
   STT Service  ──────────────────────────────────────────────────────────────────┐
   (WhisperLiveKit WS | Whisper local | Deepgram)                                 │
        │  transcribed text                                                        │
        ▼                                                                          │
   User Context Aggregator  (smart turn detection via LocalSmartTurnAnalyzerV3)   │
        │  complete user turn                                                      │
        ▼                                                                          │
   LLM Service  (AWS Bedrock — Claude Haiku 4.5)                                  │
        │  text response / tool calls                                              │
        ▼                                                                          │
   TTS Service  ──────────────────────────────────────────────────────────────────┘
   (Chatterbox Server | Piper | AWS Polly | ElevenLabs)
        │  audio out
        ▼
   Transport output  →  User
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

The transport layer (how audio enters and exits the pipeline) is configured in [src/helpers/config.py](src/helpers/config.py) and selected automatically by Pipecat's `create_transport` utility based on CLI arguments or runner configuration:

- **`webrtc`** — Browser-based, uses STUN/TURN ICE servers. The agent exposes port `7860` (HTTP for signaling) and `10000–10005/udp` (media).
- **`daily`** — Daily.co room-based WebRTC.
- **`twilio`** — FastAPI WebSocket for Twilio Media Streams.

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
uv run src/agent.py
```

**Docker:**
```bash
docker compose up nova-agent
# To also run Piper TTS locally, uncomment the piper-server service in docker-compose.yml
```

**Test STT connection standalone:**
```bash
python scripts/whisperlivekit_websocket.py
```

# State Of Things

## Current Status

The pipecat server is deployed using the current docker-compose in an EC2 instance that is exposed publicly with an HTTPS connection using Load Balancers, Target Groups, etc.

Although it is changed for some tests, the implementation we are putting the most focus on is using our managed-services for TTS and STT with Chatterbox and WhisperLivekit. This two servers are deployed on the same instance but manually (following the scripts showcased above).

## Future Status

This are some of the task we will tackle to improve the current implementation. Those that are tagged with \[OTHERS\] will be implemented by other people in the team, and those tagged with \[BLOCKED\] are blocked by other taks needed to be finished before. The untagged ones we can tackle whenever we have time.

A. \[OTHERS\] One of the experts in the team is generating images and containers for the TTS and STT servers. We should not care about this now, once these are developed we will need to include them in the docker compose.

B. \[BLOCKED:A\] Once everything is tested with docker compose, prepare whatever is necesary to deploy this to EC2, ECS or EKS depending on the needs, probably also having comparibility with GCP equivalent services.

C. \[BLOCKED:B\] Once everything is tested, we should create the CDK and GCP equivalent files for deploying this automatically using CI/CD and likely some tests.

D. \[OTHERS\] Instead of using the web ui provided by pipecat, we will advance on creating our own applications or integrations with other communication services like telephony.