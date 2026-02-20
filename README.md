# Pipecat AI Voice Agent

Agente conversacional de voz construido con [Pipecat AI](https://github.com/pipecat-ai/pipecat). Pipeline configurable de STT, LLM y TTS con soporte para multiples proveedores.

## Arquitectura

```
Browser/Phone
     |
  Transport (WebRTC / Daily / Twilio)
     |
  STT  -->  LLM  -->  TTS
     |                   |
  WhisperLiveKit    Chatterbox Server
  Deepgram          Polly / Piper
```

## Estructura del Proyecto

```
.
├── src/
│   ├── agent.py                  # Pipeline principal: Transport -> STT -> LLM -> TTS
│   └── helpers/
│       ├── config.py             # Transports, VAD, system prompt
│       ├── services.py           # Factories de STT/TTS/LLM por env vars
│       ├── tools.py              # Tool definitions para el LLM
│       ├── whisper_livekit_custom_integration.py   # Plugin STT: WhisperLiveKit streaming
│       └── chatterbox_custom_integration.py        # Plugin TTS: Chatterbox Server
├── scripts/
│   ├── piper/
│   │   ├── Dockerfile            # Imagen Docker para Piper TTS
│   │   └── run_piper.py          # Launcher del servidor Piper
│   └── whisperlivekit_websocket.py  # Script de test para WebSocket STT
├── Dockerfile                    # Imagen Docker del agente
├── docker-compose.yml
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
| `STT_SERVICE_PROVIDER` | `WHISPER-STREAM` | `WHISPER-STREAM` \| `DEEPGRAM` |
| `TTS_SERVICE_PROVIDER` | `CHATTERBOX_SERVER` | `CHATTERBOX_SERVER` \| `CHATTERBOX_SERVER_OPENAI` \| `PIPER` \| `POLLY` |
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

## Ejecucion

```bash
uv run src/agent.py
```

El agente expone un servidor WebRTC en el puerto 7860.

### Docker

```bash
docker compose up --build
```

## Proveedores de STT

### WhisperLiveKit (Streaming) — Default

STT en streaming via WebSocket. Transcribe audio mientras el usuario habla, sin esperar a que termine (conocido en el mundo de ASR como *streaming* o *live*).

A pesar de que el nombre hace referencia a Livekit, el otro framework dedicado a la gestión de VoiceAgents, el servicio es compatible con cualquier tipo de conexión Websocket. Aún más, el framework Livekit no tiene soporte para este servicio específico, así que parece ser pura coincidencia de nombres o algo por el estilo.

- Plugin custom: `src/helpers/whisper_livekit_custom_integration.py`
- Protocolo: WebSocket en `ws://{host}:{port}/asr`
- Env: `STT_SERVICE_PROVIDER=WHISPER-STREAM`

#### Despliegue del servidor WhisperLiveKit

El despliegue del servidor se puede hacer con la librería oficial ofrecida en [el repositorio de WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit). Además, como requerimiento es necesario disponer de `ffmpeg` y `portaudio` en el sistema y `pyaudio` en el entorno de Python.

Por lo tanto, los comandos para el despliegue del servidor utilizando el gestor de paquete `uv` son:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg -y
sudo apt install portaudio19-dev python3-dev
uv venv
source .venv/bin/activate
uv pip install whisperlivekit
uv pip install pyaudio
wlk --model tiny --host 0.0.0.0 --port 8000 --pcm-input --language es 
# whisperlivekit-server --model tiny --host 0.0.0.0 --port 8000 --pcm-input --language es
```

Obviamente es posible alternar entre los distintos modelos de la familia whisper cambiando el valor del parámetro `--model`, (`tiny`, `base`, `small`, `medium`, `large`), aunque es importante tener en cuenta que los modelos más grandes requieren de una mayor capacidad de cómputo y memoria, por lo que es recomendable probar primero con los modelos más pequeños para asegurarse de que el servidor funciona correctamente antes de intentar con los modelos más grandes. Además se puede configurar cuestiones como el host y puerto del servidor levantado y el idioma del modelo, que se configurará en autodetección si no se especifica. El parámetro `--pcm-input` permite enviar el audio en formato PCM sin procesar, lo que puede ser útil para reducir la latencia y mejorar la calidad de la transcripción, y es utilizado por defecto en la integración STT de Pipecat.

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

El servidor de Chatterbox utiliza la implementación [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server). Este servidor ofrece acceso a los modelos deplegados de manera local a través de una API REST con WebRTC. Además, el servidor provee una interfaz web para hacer pruebas y subir archivos de audio para la clonación de voces.

Al momento de instalar Chatterbox Server, el método más simple provisto por los desarrolladores es ejecutar el script `start.sh` con bash de Linux, `start.bat` con cmd de Windows o `start.py` con Python.

Si bien el mismo solicitaba que la versión de Python fuera mayor a 3.10, las pruebas hechas con Python 3.12 levantaban algunos errores de dependencias entre librerías propias de Python como *setuptools* y librerías externas como *numpy*. Para solucionarlo, utilizando el gestor de ambientes (uv o pip) se fijó la versión de Python a 3.10 y se instalaron los paquetes de manera manual (install requirements.txt o requirements-nvidia.txt) y ejecutando el script de server.py.

Es probable que estos problemas de dependencias se resuelvan a futuro, o que en caso de desarrollar el server con Docker, se pueda partir de una imagen con python 3.10 de base y ejecutar el script de start. Esto es también posible desde la instancia manualmente, pero es mucho más simple utilizar un gestor de paquetes porque las versiones de Python se asignan desde la AMI y puede generar issues cambiarlas.

Debido a esto, en reemplazo del script de *start*, el despliegue del servidor utilizando uv consiste en:

```bash
# instalar uv para gestión de librerías
curl -LsSf https://astral.sh/uv/install.sh | sh
# clonar repositorio
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
# crear entorno de uv con python 3.10 (y activarlo)
uv venv --python 3.10
source .venv/bin/activate
# actualizar las librerias de pip, whl y setuptools (las que daban problemas con python 3.12)
uv pip install --upgrade pip whl setuptools
# instalar requerimientos, en caso de no saber cuáles instalar se puede ejecutar el start.sh una vez aunque falle y ver cuál recomienda
uv pip install -r requirements-nvidia.txt
# ejecutar el servidor
uv run server.py
```

**NOTA:** A pesar de que el README del servidor comenta que se puede usar el modelo multilingüe con 23 idiomas, al momento de escribir esta documentación el servidor solo implementa las versiones en inglés, que al usar otros idiomas genera una voz con acento inglés. Existe un [Pull Request (PR) de fork externo]() intentando implementar esta funcionalidad, pero aún no ha sido mergeado. Es posible usar [el repositorio del fork](https://github.com/4-alok/Chatterbox-TTS-Server), pero es conveniente instalar los requerimientos del servidor desde el repositorio original:

```bash
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server
uv venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
git clone https://github.com/4-alok/Chatterbox-TTS-Server.git Chatterbox-TTS-Server-ML
cd Chatterbox-TTS-Server-ML
uv run --active server.py # sin la opción --active, uv levanta un error de que el entorno no se encuentra en la carpeta donde se está ejecutando el código.
```

### AWS Polly

TTS cloud via AWS Polly (voz Lupe, motor generative, spanish).

- Env: `TTS_SERVICE_PROVIDER=POLLY`

### Piper

TTS local/remoto open-source. Requiere un servidor Piper separado.

- Env: `TTS_SERVICE_PROVIDER=PIPER`
- Dockerfile separado en `scripts/piper/`

## LLM

### AWS Bedrock

Claude Haiku 4.5 via AWS Bedrock. Configurado con tools para busqueda de productos, carrito y ordenes.

## Metricas

El agente usa `MetricsLogObserver` de Pipecat para loggear automaticamente:
- **TTFB**: Time to first byte de cada servicio
- **Processing time**: Tiempo de procesamiento de STT, LLM y TTS
- **LLM token usage**: Prompt tokens, completion tokens, total
- **TTS usage**: Caracteres procesados

Las metricas se imprimen en stdout con el pipeline activo.
