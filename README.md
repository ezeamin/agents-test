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
├── services/
│   ├── chatterbox/
│   │   ├── Dockerfile        # Imagen Docker para Chatterbox TTS
│   │   └── config.yaml       # Config patched para Linux/Docker (paths, GPU, español)
│   └── whisperlivekit/
│       └── Dockerfile        # Imagen Docker para WhisperLiveKit STT
├── scripts/
│   ├── piper/
│   │   ├── Dockerfile        # Imagen Docker para Piper TTS
│   │   └── run_piper.py      # Launcher del servidor Piper
│   ├── whisperlivekit_websocket.py  # Script de test para WebSocket STT
│   └── test-custom-integrations/
│       ├── test_chatterbox_custom_integration.py   # Test de integración TTS: síntesis con parámetros
│       │                                           # ajustables, reporte de TTFA, análisis de gaps,
│       │                                           # guardado de WAV y reproducción opcional
│       └── test_whisper_livekit_custom_integration.py  # Test de integración STT: captura de mic,
│                                                       # imprime TranscriptionFrames; --raw para JSON crudo
├── Dockerfile                # Imagen Docker del agente Nova
├── docker-compose.yml        # nova-agent + stt-whisper + tts-chatterbox (network_mode: host para WebRTC)
├── requirements.txt
├── .env.example
├── cdk/                      # AWS CDK TypeScript: provisiona repositorios ECR
│   ├── bin/app.ts
│   ├── lib/ecr-stack.ts      # 3 repos ECR: strata/nova-agent, strata/stt-whisper, strata/tts-chatterbox
│   └── ...
└── .github/
    └── workflows/
        └── build-push-ecr.yml  # CI/CD: build + push a ECR en cada push a master
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
| `TTS_SERVICE_PROVIDER` | `CHATTERBOX_SERVER` | `CHATTERBOX_SERVER` \| `CHATTERBOX_SERVER_PIPELINED` \| `CHATTERBOX_SERVER_OPENAI` \| `PIPER` \| `POLLY` \| `ELEVENLABS` |
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

El agente usa `network_mode: host` para que `aiortc` pueda enlazarse directamente a las interfaces del host, necesario para que STUN descubra la IP pública correcta en EC2. Con `EC2_HOST=localhost` en `.env` los tres servicios se comunican via `localhost`.

Los servicios de STT y TTS son opcionales mediante **profiles**. Usarlos solo cuando se usan los proveedores GPU locales (WhisperLiveKit / Chatterbox); omitirlos cuando se usan APIs cloud (Deepgram, Polly, ElevenLabs):

```bash
# Stack completo (agente + STT GPU + TTS GPU):
docker compose --profile gpu-all up --build

# Solo el agente (STT/TTS via APIs cloud):
docker compose up --build

# Servicios individuales:
docker compose --profile gpu-stt up --build   # agente + stt-whisper
docker compose --profile gpu-tts up --build   # agente + tts-chatterbox
```

Para usar imágenes pre-buildeadas desde ECR en lugar de buildear localmente, setear las variables en `.env`:

```bash
NOVA_AGENT_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/strata/nova-agent:latest
STT_WHISPER_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/strata/stt-whisper:latest
TTS_CHATTERBOX_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/strata/tts-chatterbox:latest
```

```bash
docker compose --profile gpu-all pull   # descarga desde ECR
docker compose --profile gpu-all up     # corre sin buildear
```

### Test de conexion STT

```bash
python scripts/whisperlivekit_websocket.py
```

## ECR y CI/CD

Los repositorios ECR se provisionan con CDK (una sola vez por cuenta/región):

```bash
cd cdk
npm install
npx cdk bootstrap   # solo la primera vez
npx cdk deploy      # crea strata/nova-agent, strata/stt-whisper, strata/tts-chatterbox en ECR
```

El workflow `.github/workflows/build-push-ecr.yml` buildea y pushea las tres imágenes a ECR automáticamente en cada push a `master`. También se puede disparar manualmente desde la pestaña Actions de GitHub.

**Secrets requeridos en GitHub** (Settings → Secrets and variables → Actions):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`
- `AWS_ACCOUNT_ID`

Cada imagen se tagea con `latest` y con el SHA corto del commit (`sha-abc1234`) para poder hacer rollback a cualquier build anterior.

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

**Nota de protocolo:** WhisperLiveKit actualiza `lines[0]` in-place en cada
mensaje (no agrega entradas nuevas). El plugin usa un tracker basado en contenido
(`_last_lines_text`) para detectar cambios y emitir solo el delta como
`TranscriptionFrame`. Sin este mecanismo, el agregador solo recibiría las
primeras palabras del turno.

**Test de integración:**
```bash
# Con el servidor corriendo (docker compose --profile gpu-stt up):
python scripts/test-custom-integrations/test_whisper_livekit_custom_integration.py
# Para ver los mensajes JSON crudos del servidor:
python scripts/test-custom-integrations/test_whisper_livekit_custom_integration.py --raw
```

#### Despliegue del servidor WhisperLiveKit

**Docker (recomendado):**

```bash
docker compose up --build stt-whisper
```

El modelo y el idioma se configuran via variables de entorno en `.env`:

```
WHISPER_MODEL=medium   # tiny | base | small | medium | large
WHISPER_LANG=es
```

**Manual:**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg portaudio19-dev python3-dev -y
uv venv && source .venv/bin/activate
uv pip install whisperlivekit pyaudio
wlk --model medium --host 0.0.0.0 --port 8000 --pcm-input --language es
```

El parámetro `--pcm-input` es requerido por la integración de Pipecat.

### Deepgram

STT cloud via API de Deepgram (modelo nova-3, spanish).

- Env: `STT_SERVICE_PROVIDER=DEEPGRAM`, `DEEPGRAM_API_KEY=...`

## Proveedores de TTS

### Chatterbox Server — Default

TTS via servidor Chatterbox con soporte para voces predefinidas y clonadas. Detecta automaticamente el modo de voz consultando `/get_predefined_voices`.

- Plugin custom: `src/helpers/chatterbox_custom_integration.py`
- Endpoints soportados: `/tts` (default) y `/v1/audio/speech` (OpenAI-compatible)
- Env: `TTS_SERVICE_PROVIDER=CHATTERBOX_SERVER` o `CHATTERBOX_SERVER_OPENAI`

**Estrategia de pipelining:** El servidor Chatterbox genera el audio completo
antes de enviarlo (no hay streaming verdadero — hay un PR upstream pendiente).
`ChatterboxServerTTSPipelined` (`CHATTERBOX_SERVER_PIPELINED`) lanza una
request `/tts` por oración inmediatamente sin esperar a que la anterior
termine de generarse. Las respuestas se encolan en orden y se reproducen
secuencialmente, eliminando el gap entre oraciones que produce la clase base.

> **Nota:** El plugin asume un header WAV estándar de 44 bytes para extraer el
> PCM crudo de la respuesta. Si en algún momento el servidor envía headers de
> longitud variable, habría que parsearlos en lugar de hacer un skip fijo.

`ChatterboxServerTTS` (`CHATTERBOX_SERVER`, default) es el fallback estable
sin pipelining — una request a la vez, sin asumir nada del header.

> **Deprecated:** `ChatterboxServerTTSSentenceSplit` — el enfoque anterior
> de dividir oraciones en el cliente resultó en mayor latencia total por el
> overhead de múltiples requests secuenciales. Reemplazado por
> `ChatterboxServerTTSPipelined`.

**Test de integración:**
```bash
# Con el servidor corriendo (docker compose --profile gpu-tts up):
python scripts/test-custom-integrations/test_chatterbox_custom_integration.py \
  "Soy Nova tu asistente de Strata Sportiva. ¿En qué puedo ayudarte?"

# Guardar audio para inspección:
python scripts/test-custom-integrations/test_chatterbox_custom_integration.py \
  --save output.wav "Hola, ¿cómo estás?"
```

#### Despliegue del servidor Chatterbox

Utiliza [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server).

**Docker (recomendado):**

```bash
docker compose up --build tts-chatterbox
```

El container clona el repositorio en el build, aplica nuestro `config.yaml` patched (ver `services/chatterbox/`) y arranca el servidor en el puerto 8004. Los modelos se cachean en el volumen `./cache` para no re-descargarlos en cada reinicio.

**Manual:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
uv venv --python 3.10 && source .venv/bin/activate
uv pip install --upgrade pip setuptools wheel
uv pip install -r requirements-nvidia.txt
uv run server.py
```

> **Nota multilingüe:** Si se necesita soporte para español y el servidor solo genera voz en inglés, el fork [4-alok/Chatterbox-TTS-Server](https://github.com/4-alok/Chatterbox-TTS-Server) añade soporte multilingüe. Sus dependencias están desactualizadas, por lo que hay que instalar los requirements del repo de devnen y correr el server del fork:
> ```bash
> git clone https://github.com/devnen/Chatterbox-TTS-Server.git
> cd Chatterbox-TTS-Server && uv venv && source .venv/bin/activate
> pip install -r requirements.txt && cd ..
> git clone https://github.com/4-alok/Chatterbox-TTS-Server.git Chatterbox-TTS-Server-ML
> cd Chatterbox-TTS-Server-ML && uv run --active server.py
> ```
> Ver también `services/chatterbox/prev.Dockerfile` para la versión containerizada de este enfoque.

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
