"""Configuración del agente de voz"""
import os
from dotenv import load_dotenv

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

load_dotenv(override=True)

# Configurar OpenTelemetry si está disponible
try:
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    from pipecat.utils.tracing.setup import setup_tracing
    
    console_exporter = ConsoleSpanExporter()
    setup_tracing(
        service_name="pipecat-voice-agent",
        exporter=console_exporter,
        console_export=True,
    )
except ImportError:
    pass

# Configuración de transports
transport_params = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
    ),
}

# Mensaje del sistema para el LLM
SYSTEM_MESSAGE = (
    "Sos un asistente conectado en un pipeline stt + llm + tts, que repite lo mismo que se interpretó en la fase anterior a modo de probar el modelo stt. "
    "Respondé corto, claro y sin vueltas. No formatees el texto, ya que los caracteres especiales se leen en voz alta."
    "Tu respuesta será hablada en voz alta. Limitate a responder exactamente lo que escuchaste, nada más. No proceses nada nuevo."
)
