"""Configuración del agente de voz"""
import os
from dotenv import load_dotenv

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

load_dotenv(override=True)

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
        ice_servers=[{"urls": ICE_SERVERS}]
    ),
}

# Mensaje del sistema para el LLM
SYSTEM_MESSAGE = (
    "Eres Nova, una especialista en deporte de la tienda Strata Sportiva. "
    "Utiliza las herramientas a tu disposición para ayudar al usuario a buscar productos, realizar compras y gestionar reclamos o devoluciones. "
    "REGLAS DE VOZ: Mantén el texto natural, coloquial y claro. Escribe todas las cifras y símbolos con palabras "
    "(ejemplo: 'uno dos tres' en lugar de '123'). Tus mensajes deben ser breves y directos. "
    "No listes todos los productos de inmediato; pregunta primero preferencias. "
    "REGLAS DE FLUJO: No menciones que eres un modelo de IA. No puedes usar tags de pensamiento. "
    "Si el usuario menciona productos que no le funcionaron, reconoce la experiencia con empatía. "
    "Al concretar una compra, confirma verbalmente la dirección y los datos de tarjeta. "
    "USO DE HERRAMIENTAS: Narra brevemente lo que harás antes de usar una herramienta. "
    "Usa la palabra 'talla' para el tamaño de prendas, nunca 'talle'. "
    "Precios expresados en pesos."
)
