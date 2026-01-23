"""Servicios de STT, TTS y LLM"""
import os
import ssl
import aiohttp

from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.piper.tts import PiperTTSService

# Descargar recursos de NLTK necesarios para PiperTTS
try:
    import nltk
    try:
        # Intentar descargar con SSL normal
        nltk.download('punkt_tab', quiet=True)
    except Exception:
        # Si falla por SSL, intentar sin verificación
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context
        nltk.download('punkt_tab', quiet=True)
except ImportError:
    pass


def create_stt_service():
    """Crea y configura el servicio de Speech-to-Text (Whisper)"""
    return WhisperSTTService(
        model="medium",
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
