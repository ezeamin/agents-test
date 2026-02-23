# Pipecat AI Voice Agent — Nova

Agente conversacional de voz construido con [Pipecat AI](https://github.com/pipecat-ai/pipecat). Pipeline configurable de STT, LLM y TTS con soporte para multiples proveedores.

## Arquitectura

```
Browser
   │  WebRTC (SmallWebRTCTransport)
   ▼
agent.py  ──  FastAPI server  ──  /api/offer (WebRTC signaling)
                                  /ws/debug  (debug events → frontend)
                                  /          (debug frontend)
   │
   ▼
pipelines/nova.py
   │
   ├── STT  →  [DebugCapture]  →  UserAggregator
   │   WhisperLiveKit / Deepgram / Whisper local
   │
   ├── LLM  →  [DebugCapture]
   │   AWS Bedrock (Claude Haiku 4.5)
   │
   └── TTS  →  [DebugCapture]  →  audio out
       Chatterbox Server / Polly / Piper / ElevenLabs
```

## Estructura del Proyecto

```
.
├── src/
│   ├── agent.py              # FastAPI server: WebRTC signaling + debug WS + static
│   ├── frontend/
│   │   └── index.html        # Debug UI: mic mute, STT transcript, LLM text, event log
│   ├── pipelines/
│   │   └── nova.py           # Pipeline: DebugBroadcaster, DebugFrameCapture, run_bot
│   └── helpers/
│       ├── config.py         # ICE_SERVERS, SYSTEM_MESSAGE
│       ├── services.py       # Factories de STT/TTS/LLM por env vars
│       ├── tools.py          # Tool definitions para el LLM
│       ├── whisper_livekit_custom_integration.py   # Plugin STT: WhisperLiveKit streaming
│       └── chatterbox_custom_integration.py        # Plugin TTS: Chatterbox Server
├── scripts/
│   ├── piper/
│   │   ├── Dockerfile        # Imagen Docker para Piper TTS
│   │   └── run_piper.py      # Launcher del servidor Piper
│   └── whisperlivekit_websocket.py  # Script de test para WebSocket STT
├── Dockerfile                # Imagen Docker del agente
├── docker-compose.yml        # network_mode: host (necesario para WebRTC en EC2)
├── requirements.txt
└── .env.example
```

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Credenciales AWS con acceso a Bedrock

## Instalacion

```bash
uv pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus valores
```

## Variables de Entorno

| Variable | Default | Descripcion |
|---|---|---|
| `STT_SERVICE_PROVIDER` | `WHISPER_STREAM` | `WHISPER_STREAM` \| `WHISPER` \| `DEEPGRAM` |
| `TTS_SERVICE_PROVIDER` | `CHATTERBOX_SERVER` | `CHATTERBOX_SERVER` \| `CHATTERBOX_SERVER_OPENAI` \| `PIPER` \| `POLLY` \| `ELEVENLABS` |
| `ICE_SERVERS` | Google STUN | URLs ICE separadas por comas. Ver nota de producción abajo. |
| `EC2_HOST` | — | Host por defecto para todos los servidores remotos |
| `EC2_HOST_WHISPER_STREAM` | `EC2_HOST` | Override para el servidor WhisperLiveKit |
| `EC2_HOST_CHATTERBOX` | `EC2_HOST` | Override para el servidor Chatterbox |
| `EC2_HOST_PIPER` | `EC2_HOST` | Override para el servidor Piper |
| `EC2_WHISPER_PORT` | `8000` | Puerto del servidor WhisperLiveKit |
| `EC2_CHATTERBOX_PORT` | `8004` | Puerto del servidor Chatterbox |
| `EC2_PIPER_PORT` | `5002` | Puerto del servidor Piper |
| `AWS_ACCESS_KEY_ID` | — | Credenciales AWS (Bedrock / Polly) |
| `AWS_SECRET_ACCESS_KEY` | — | |
| `AWS_SESSION_TOKEN` | — | |
| `AWS_DEFAULT_REGION` | `us-east-1` | |
| `DEEPGRAM_API_KEY` | — | Solo si `STT_SERVICE_PROVIDER=DEEPGRAM` |
| `ELEVENLABS_API_KEY` | — | Solo si `TTS_SERVICE_PROVIDER=ELEVENLABS` |

## Ejecucion

```bash
uv run src/agent.py   # http://localhost:7860
```

### Docker (EC2)

El agente usa `network_mode: host` para que `aiortc` pueda enlazarse directamente a las interfaces del host. Esto es necesario para que STUN descubra la IP pública correcta en EC2. Con `EC2_HOST=localhost` en `.env`:

```bash
docker compose up --build
```

### Test de conexion STT

```bash
python scripts/whisperlivekit_websocket.py
```

## ICE Servers — Nota de Produccion

La configuracion por defecto usa STUN de Google, suficiente para desarrollo pero no para produccion. En redes con NAT simétrico, firewalls corporativos o desde dispositivos móviles puede fallar. **Para produccion usar un servidor TURN.**

Proveedores compatibles (configurar via `ICE_SERVERS` en `.env`):
- **Twilio NTS** — Pipecat tiene transporte nativo de Twilio
- **Daily** — Pipecat tiene transporte nativo de Daily
- **Telnyx** — Pipecat tiene transporte nativo de Telnyx
- **Metered.ca** — Tier gratuito disponible
- **Cloudflare TURN** — En beta, tier gratuito generoso
- **Coturn** — Self-hosted, puede correr como sidecar en la misma instancia EC2

## Proveedores de STT

### WhisperLiveKit (Streaming) — Default

STT en streaming via WebSocket. Transcribe audio mientras el usuario habla sin esperar a que termine.

- Plugin custom: `src/helpers/whisper_livekit_custom_integration.py`
- Protocolo: WebSocket en `ws://{host}:{port}/asr`
- Env: `STT_SERVICE_PROVIDER=WHISPER_STREAM`

#### Despliegue del servidor WhisperLiveKit

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg portaudio19-dev python3-dev -y
uv venv && source .venv/bin/activate
uv pip install whisperlivekit pyaudio
wlk --model tiny --host 0.0.0.0 --port 8000 --pcm-input --language es
```

Modelos disponibles: `tiny`, `base`, `small`, `medium`, `large`. El parámetro `--pcm-input` es requerido por la integración de Pipecat.

### Deepgram

STT cloud via API de Deepgram (modelo nova-3, spanish).

- Env: `STT_SERVICE_PROVIDER=DEEPGRAM`, `DEEPGRAM_API_KEY=...`

## Proveedores de TTS

### Chatterbox Server — Default

TTS via servidor Chatterbox con soporte para voces predefinidas y clonadas. Detecta automaticamente el modo de voz consultando `/get_predefined_voices`.

- Plugin custom: `src/helpers/chatterbox_custom_integration.py`
- Endpoints soportados: `/tts` (default) y `/v1/audio/speech` (OpenAI-compatible)
- Env: `TTS_SERVICE_PROVIDER=CHATTERBOX_SERVER` o `CHATTERBOX_SERVER_OPENAI`

#### Despliegue del servidor Chatterbox

Utiliza [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server). Requiere Python 3.10 (hay conflictos de dependencias con 3.12):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
uv venv --python 3.10 && source .venv/bin/activate
uv pip install --upgrade pip whl setuptools
uv pip install -r requirements-nvidia.txt
uv run server.py
```

**Nota multilingüe:** Al momento de escribir esto el servidor solo implementa voces en inglés. Para español usar [el fork con soporte multilingüe](https://github.com/4-alok/Chatterbox-TTS-Server), instalando requirements desde el repo original:

```bash
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server && uv venv && source .venv/bin/activate
pip install -r requirements.txt && cd ..
git clone https://github.com/4-alok/Chatterbox-TTS-Server.git Chatterbox-TTS-Server-ML
cd Chatterbox-TTS-Server-ML
uv run --active server.py
```

### AWS Polly

TTS cloud via AWS Polly (voz Lupe, motor generative, español).

- Env: `TTS_SERVICE_PROVIDER=POLLY`

### Piper

TTS local/remoto open-source. Requiere un servidor Piper separado.

- Env: `TTS_SERVICE_PROVIDER=PIPER`
- Dockerfile separado en `scripts/piper/`

## LLM

### AWS Bedrock

Claude Haiku 4.5 via AWS Bedrock. Configurado con tools para búsqueda de productos, carrito y órdenes.

## Metricas

El agente usa `MetricsLogObserver` de Pipecat para loggear automaticamente:
- **TTFB**: Time to first byte de cada servicio
- **Processing time**: Tiempo de procesamiento de STT, LLM y TTS
- **LLM token usage**: Prompt tokens, completion tokens, total
- **TTS usage**: Caracteres procesados

Las metricas se imprimen en stdout con el pipeline activo.

## Debug Frontend

Accesible en `http://<host>:7860`. Incluye:
- Botón conectar/desconectar y silenciar micrófono
- Panel **Usuario (STT)**: muestra transcripcion interim en tiempo real y la transcripcion final
- Panel **Nova (LLM)**: muestra el texto generado por el LLM en streaming, con indicador de cuando el TTS está hablando
- **Debug Log**: eventos del pipeline con timestamps y color por tipo
