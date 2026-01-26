"""Servicios de STT, TTS y LLM"""
import os
import ssl
import aiohttp

from deepgram import LiveOptions
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.aws.llm import AWSBedrockLLMService
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
    if False:
        return OpenAISTTService(
            model="mistralai/Voxtral-Mini-3B-2507",
            base_url="http://localhost:8000/v1",
            api_key="NONE"
        )
    elif False:
        return WhisperSTTService(
            model="medium",
            device="cpu",
            compute_type="int8", 
            language="es",
        )
    elif True:
        live_options = LiveOptions(
            model="nova-3",
            language="es-419",
            interim_results=True,
            smart_format=True,
            punctuate=True
        )
        return DeepgramSTTService(
            live_options=live_options,
            api_key=os.getenv("DEEPGRAM_API_KEY")
        )


def create_tts_service(session: aiohttp.ClientSession):
    """Crea y configura el servicio de Text-to-Speech (Piper)"""
    return PiperTTSService(
        base_url="http://localhost:5002",
        aiohttp_session=session,
    )


def create_llm_service():
    """Crea y configura el servicio de LLM (AWS Bedrock)"""
    return AWSBedrockLLMService(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
