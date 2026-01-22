"""Servicios de STT, TTS y LLM"""
import os
import aiohttp

from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.piper.tts import PiperTTSService


def create_stt_service():
    """Crea y configura el servicio de Speech-to-Text (Whisper)"""
    return WhisperSTTService(
        model="small",
        device="cpu",
        compute_type="int8", 
        language="es",
    )


def create_tts_service(session: aiohttp.ClientSession):
    """Crea y configura el servicio de Text-to-Speech (Piper)"""
    return PiperTTSService(
        base_url="http://localhost:5002",
        aiohttp_session=session,
    )


def create_llm_service():
    """Crea y configura el servicio de LLM (Groq)"""
    return GroqLLMService(
        api_key=os.getenv("GROQ_API_KEY"),
        model="groq/compound",
    )
