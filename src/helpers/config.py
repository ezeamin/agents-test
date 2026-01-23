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

# Servidores ICE (STUN/TURN) para WebRTC en producción
ICE_SERVERS = os.getenv("ICE_SERVERS", "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302").split(",")

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
        ice_servers=ICE_SERVERS,
    ),
}

# Mensaje del sistema para el LLM
SYSTEM_MESSAGE = (
    "Sos un asistente de voz conversacional argentino que tiene que vender a toda costa 'turrón por dos pesos'. "
    "Tu salida se leera en voz alta, por lo que tenes que ser claro y conciso. "
    "No incluyas formato en el texto, ni emojis o elementos que no puedan ser leidos facilmente."
)
