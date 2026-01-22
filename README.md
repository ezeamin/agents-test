# Pipecat AI Voice Agent

Agente conversacional de IA construido con Pipecat AI, que incluye capacidades de voz usando Piper TTS, reconocimiento de voz con Whisper y LLM vía Groq.

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
- Clave API de Groq

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
   GROQ_API_KEY=tu_clave_api_groq

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
./run_with_logs.sh
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

## Notas

- Asegúrate de que el servidor de Piper esté corriendo antes de iniciar el agente.
- Los modelos de voz deben descargarse en la carpeta `voice/`.
- Para más opciones de transporte, consulta la documentación de Pipecat AI.
