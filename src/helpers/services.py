"""Servicios de STT, TTS y LLM"""
import os
import ssl
import aiohttp

from deepgram import LiveOptions
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.aws.llm import AWSBedrockLLMService
from pipecat.services.aws.tts import PollyTTSService
from pipecat.services.piper.tts import PiperTTSService
from pipecat.services.xtts.tts import XTTSService

from helpers.whisper_livekit_custom_integration import WhisperLiveKitSTT

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
    stt_service_provider = os.getenv("STT_SERVICE_PROVIDER", "WHISPER-STREAM")
    if stt_service_provider == "VOXTRAL":
        return OpenAISTTService(
            model="mistralai/Voxtral-Mini-3B-2507",
            base_url="http://localhost:8000/v1",
            api_key="NONE"
        )
    elif stt_service_provider == "WHISPER":
        return WhisperSTTService(
            model="medium",
            device="cpu",
            compute_type="int8", 
            language="es",
        )
    elif stt_service_provider == "WHISPER-STREAM":
        ec2_host = os.getenv('EC2_HOST_WHISPER_STREAM', os.getenv('EC2_HOST'))
        if not ec2_host:
            raise ValueError("Must set EC2_HOST")
        return WhisperLiveKitSTT(
            url=f"ws://{ec2_host}:{os.getenv('EC2_WHISPER_PORT', 8000)}/asr",
        )
    elif stt_service_provider == "DEEPGRAM":
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
    tts_service_provider = os.getenv("TTS_SERVICE_PROVIDER", "POLLY")
    if tts_service_provider == "PIPER":
        base_url = os.getenv("PIPER_BASE_URL", "http://localhost:5002")
        return PiperTTSService(
            base_url=base_url,
            aiohttp_session=session,
        )
    elif tts_service_provider == "XTTS":
        return XTTSService(
            voice_id="Claribel Dervla",
            base_url="http://localhost:5002",
            aiohttp_session=session,
        )
    elif tts_service_provider == "CHATTERBOX":
        ec2_host = os.getenv('EC2_HOST_CHATTERBOX', os.getenv('EC2_HOST'))
        if not ec2_host:
            raise ValueError("Must set EC2_HOST")
        return OpenAITTSService(
            base_url=f"http://{ec2_host}:{os.getenv('EC2_CHATTERBOX_PORT', 8004)}/v1",
            voice="",
            api_key="NONE"
        )
    elif tts_service_provider == "POLLY":
        return PollyTTSService(
            voice="Lupe",
            speech_engine="generative",
            language="es-US"
        )


def create_llm_service():
    """Crea y configura el servicio de LLM (AWS Bedrock)"""
    return AWSBedrockLLMService(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id")),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key")),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token")),
        region=os.getenv("AWS_DEFAULT_REGION", os.getenv("aws_default_region", "us-east-1")),
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
