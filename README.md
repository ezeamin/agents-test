# Pipecat AI Voice Agent

Agente conversacional de IA construido con Pipecat AI, que incluye capacidades de voz usando Piper TTS, reconocimiento de voz con Whisper y LLM vía AWS Bedrock.

## Estructura del Proyecto

```
.
├── src/
│   ├── agent.py              # Agente principal con pipeline STT → LLM → TTS
│   ├── run_piper.py          # Servidor Piper TTS
│   └── helpers/              # Módulos de soporte
│       ├── config.py         # Configuración y transports
│       ├── services.py       # Servicios STT/TTS/LLM
│       └── processors.py     # Procesadores customizados
├── logs/                     # Logs generados automáticamente
├── voice/                    # Modelos de voz Piper (.onnx)
├── run_with_logs.sh          # Script para ejecutar el agente con logging
├── run_piper.sh              # Script para ejecutar el servidor TTS
├── requirements.txt          # Dependencias Python
└── .env                      # Variables de entorno (no versionado)
```

## Requisitos Previos

- Python 3.8 o superior
- uv (gestor de paquetes Python)
- Credenciales de AWS (Access Key y Secret Key) con acceso a Bedrock

## Instalación

1. **Instalar dependencias:**

   ```bash
   uv pip install -r requirements.txt
   ```

2. **Descargar modelos de voz:**

   Descarga los archivos `.onnx` y `.onnx.json` en `./voice/`.
   Por ejemplo, para `es_MX-claude-high`:
   - [Voces disponibles en Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main)

3. **Configurar variables de entorno:**

   Crea `.env` en la raíz:

   ```env
   AWS_ACCESS_KEY_ID=tu_access_key_id
   AWS_SECRET_ACCESS_KEY=tu_secret_access_key
   AWS_REGION=us-east-1

   CURRENT_VOICE=es_MX-claude-high.onnx
   CURRENT_VOICE_CONFIG=es_MX-claude-high
   PIPER_PORT=5002
   ```

## Uso

### Ejecutar con logs completos (recomendado)

```bash
# Terminal 1: Servidor TTS
./run_piper.sh

# Terminal 2: Agente con logging
./run_agent.sh
```

Los logs se guardan automáticamente en `logs/pipeline_debug.log` con métricas detalladas de OpenTelemetry (tokens, latencias, transcripciones).

### Ejecutar manualmente

```bash
# Terminal 1: Servidor TTS
uv run python src/run_piper.py

# Terminal 2: Agente
uv run python src/agent.py
```

El agente estará listo para recibir conexiones y procesar audio/texto en tiempo real.

### Diagnóstico Bedrock (UnrecognizedClientException)

Si ves "The security token included in the request is invalid" y las credenciales son correctas:

1. **Reproducir la llamada a Bedrock** (mismas credenciales que el agente) y ver la respuesta completa de AWS:

   ```bash
   uv run python scripts/check_bedrock.py
   ```

   El script prueba STS y Bedrock ConverseStream; si falla, muestra **Code**, **Message** y **RequestId** para depurar o contactar soporte AWS.

2. **Probar modelo base en región** (sin perfil cross-region `us.anthropic`). En `.env` añade:

   ```env
   BEDROCK_MODEL_ID=anthropic.claude-haiku-4-5-20251001-v1:0
   ```

   Si así funciona, el fallo puede ser del perfil de inferencia (permisos/SCP en otras regiones).

## Notas

- Asegúrate de que el servidor de Piper esté corriendo antes de iniciar el agente.
- Los modelos de voz deben descargarse en la carpeta `voice/`.
- Para más opciones de transporte, consulta la documentación de Pipecat AI.
