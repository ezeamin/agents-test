# Helpers – Servicios STT, TTS y LLM

Este módulo (`services.py`, `config.py`, `processors.py`) define los servicios de **Speech-to-Text (STT)**, **Text-to-Speech (TTS)** y **LLM** usados por el agente de voz, y su configuración mediante variables de entorno.

---

## Índice

1. [Servicio TTS (Text-to-Speech)](#servicio-tts-text-to-speech)
2. [ChatterboxTTSService (implementación propia)](#chatterboxttsservice-implementación-propia)
3. [Servicio STT (Speech-to-Text)](#servicio-stt-speech-to-text)
4. [Servicio LLM](#servicio-llm)
5. [Variables de entorno](#variables-de-entorno)

---

## Servicio TTS (Text-to-Speech)

El TTS se elige con **`TTS_SERVICE_PROVIDER`**. Hay tres proveedores:

| Proveedor   | Descripción |
|------------|-------------|
| **CHATTERBOX** | Servidor Chatterbox-TTS (API propia, POST `/tts`). **Por defecto.** |
| **PIPER**      | Piper TTS local (HTTP). |
| **XTTS**       | XTTS (ej. Coqui), voz `Claribel Dervla`. |

La función `create_tts_service(session)` devuelve la instancia del servicio configurado según `TTS_SERVICE_PROVIDER` y las variables de entorno.

---

## ChatterboxTTSService (implementación propia)

Chatterbox **no usa la API de OpenAI**. Expone su propia API: **POST `{base_url}/tts`** con un JSON específico. Por eso implementamos **`ChatterboxTTSService`** en lugar de usar `OpenAITTSService` de Pipecat.

### Qué hace esta clase

1. **Envía POST a `{base_url}/tts`** con un payload JSON (texto, modo de voz, formato, parámetros de generación).
2. **Acepta dos modos de voz**:
   - **`predefined`**: voces que están en la carpeta `voices/` del servidor (ej. `Elena.wav`, `Emily.wav`, `Abigail.wav`).
   - **`clone`**: clonado a partir de un archivo de audio de referencia (ej. `Juanma.wav`).
3. **Recibe la respuesta** en WAV (binario) o en JSON con audio en base64 (`audio`, `content` o `data`).
4. **Decodifica el WAV** a PCM y emite **`TTSAudioRawFrame`** en chunks (tamaño `TTS_CHUNK_SIZE` = 4096 bytes) para que Pipecat los envíe por WebRTC.

Hereda de **`TTSService`** de Pipecat e implementa **`run_tts(text)`** como generador asíncrono que emite:

- `TTSStartedFrame`
- `TTSAudioRawFrame(chunk, sample_rate, num_channels)` por cada trozo de PCM
- `TTSStoppedFrame`
- o `ErrorFrame` si hay error HTTP, timeout o excepción

### Parámetros del payload (alineados con el servidor)

Valores por defecto ajustados para coincidir con un POST que funciona en el servidor:

| Parámetro                | Default   | Descripción |
|--------------------------|-----------|-------------|
| `voice_mode`             | `predefined` | `predefined` (voces en `voices/`) o `clone` (audio de referencia). |
| `predefined_voice_id`    | `Elena.wav`  | Archivo en `voices/`. Se añade `.wav` si no termina en `.wav`. |
| `reference_audio_filename` | `Juanma.wav` (clone) | Archivo de referencia en modo clone. |
| `language`              | `es`      | Código de idioma. |
| `output_format`         | `wav`     | Formato de salida. |
| `split_text`            | `true`    | Partir texto en chunks en el servidor. |
| `chunk_size`             | `240`     | Tamaño de chunk de texto (caracteres). |
| `temperature`            | `0.8`     | Temperatura de generación. |
| `exaggeration`           | `1.3`     | Exageración. |
| `cfg_weight`             | `0.5`     | Peso de CFG. |
| `speed_factor`           | `1.0`     | Velocidad de habla. |
| `seed`                   | `1775`    | Semilla (evitar `0` por bugs en el servidor T3). |
| `timeout`                | `60`      | Timeout HTTP en segundos. |

### Flujo interno

1. Construir `payload` con los parámetros anteriores y `text`.
2. Si `voice_mode == "predefined"` → incluir `predefined_voice_id`.
3. Si `voice_mode == "clone"` → incluir `reference_audio_filename`.
4. `POST` con `httpx.AsyncClient(timeout=self._timeout)`.
5. Si `status_code != 200` → `yield ErrorFrame(...)` y terminar.
6. Leer cuerpo: si `Content-Type` es `application/json`, decodificar base64 desde `audio` / `content` / `data`; si no, asumir WAV binario.
7. Abrir WAV con `wave.open(io.BytesIO(wav_bytes), "rb")`, leer sample rate y canales, y leer todos los frames PCM.
8. Emitir `TTSStartedFrame`, luego `TTSAudioRawFrame` por cada chunk de PCM, y finalmente `TTSStoppedFrame`.
9. Capturar `httpx.TimeoutException` y otras excepciones y emitir `ErrorFrame` con mensaje claro.

---

## Servicio STT (Speech-to-Text)

Se elige con **`STT_SERVICE_PROVIDER`**:

| Proveedor | Descripción |
|-----------|-------------|
| **WHISPER** (default) | Whisper local, modelo `medium`, `int8`, idioma `es`. |
| **VOXTRAL** | Voxtral (Mistral), base_url local. |
| **DEEPGRAM** | Deepgram, modelo `nova-3`, idioma `es-419`. Requiere `DEEPGRAM_API_KEY`. |

`create_stt_service()` devuelve la instancia correspondiente. Los servicios **OpenAISTTService** y **DeepgramSTTService** deben estar importados donde se usen (en el código actual se referencian pero las importaciones pueden estar en otro módulo o entorno).

---

## Servicio LLM

- **Proveedor**: AWS Bedrock (`AWSBedrockLLMService`).
- **Modelo por defecto**: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`.
- **Credenciales**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, opcionalmente `AWS_SESSION_TOKEN`, y `AWS_DEFAULT_REGION` (por defecto `us-east-1`).

`create_llm_service()` llama a `check_aws_bedrock_credentials()` (que con `AWS_DEBUG=1` hace diagnóstico de STS y Bedrock) y devuelve la instancia de `AWSBedrockLLMService`.

---

## Variables de entorno

### TTS (Chatterbox – `TTS_SERVICE_PROVIDER=CHATTERBOX`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TTS_BASE_URL` | `http://ec2-18-216-95-105.us-east-2.compute.amazonaws.com:8004` | Base URL del servidor Chatterbox (sin `/v1` ni `/tts`). |
| `TTS_VOICE_MODE` | `predefined` | `predefined` o `clone`. |
| `TTS_PREDEFINED_VOICE_ID` | `Elena.wav` | Voz en `voices/` (se añade `.wav` si no tiene extensión). |
| `TTS_REFERENCE_AUDIO` | `Juanma.wav` (clone) / `Elena.wav` (predefined) | Archivo de referencia en modo clone, o fallback en predefined. |
| `TTS_LANGUAGE` | `es` | Código de idioma. |
| `TTS_OUTPUT_FORMAT` | `wav` | Formato de salida. |
| `TTS_SPLIT_TEXT` | `true` | Partir texto en el servidor. |
| `TTS_CHUNK_SIZE` | `240` | Tamaño de chunk de texto. |
| `TTS_TEMPERATURE` | `0.8` | Temperatura. |
| `TTS_EXAGGERATION` | `1.3` | Exaggeration. |
| `TTS_CFG_WEIGHT` | `0.5` | CFG weight. |
| `TTS_SPEED_FACTOR` | `1` | Velocidad. |
| `TTS_SEED` | `1775` | Semilla (no usar `0`). |
| `TTS_TIMEOUT` | `60` | Timeout HTTP (segundos). |

### TTS (Piper / XTTS)

- **PIPER**: `PIPER_BASE_URL` (default `http://localhost:5002`).
- **XTTS**: base y voz fijas en código (se pueden parametrizar luego si hace falta).

### STT

- `STT_SERVICE_PROVIDER`: `WHISPER` | `VOXTRAL` | `DEEPGRAM`.
- **DEEPGRAM**: `DEEPGRAM_API_KEY`.

### LLM (AWS Bedrock)

- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (opcional), `AWS_DEFAULT_REGION`.
- `AWS_DEBUG=1`: activa el diagnóstico de credenciales y Bedrock.

### Config / transporte

- VAD y transporte: ver `config.py` (ICE servers, `VAD_PARAMS`, `transport_params`).

---

## Resumen de lo implementado

1. **ChatterboxTTSService**: cliente TTS propio para la API Chatterbox (POST `/tts`), con modos predefined y clone, parámetros alineados con el servidor, manejo de WAV/binario y JSON base64, y emisión de frames Pipecat.
2. **Integración con Pipecat**: herencia de `TTSService`, uso de `TTSStartedFrame`, `TTSAudioRawFrame`, `TTSStoppedFrame`, `ErrorFrame` y chunk size constante para PCM.
3. **Configuración por entorno**: todos los parámetros relevantes del TTS Chatterbox (y del resto de servicios) configurables vía variables de entorno sin tocar código.
4. **Robustez**: timeout configurable, manejo de errores HTTP y de excepciones, y evitación de `seed=0` por bugs conocidos en el motor T3 del servidor.

Para más detalle del pipeline (STT → LLM → TTS) y del agente, ver la documentación del proyecto y `agent.py`.
