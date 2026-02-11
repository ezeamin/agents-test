"""Servicios de STT, TTS y LLM"""
import os
import aiohttp

from deepgram import LiveOptions
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.aws.llm import AWSBedrockLLMService
from pipecat.services.aws.tts import PollyTTSService
from pipecat.services.piper.tts import PiperTTSService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from helpers.whisper_livekit_custom_integration import WhisperLiveKitSTT
from helpers.chatterbox_custom_integration import ChatterboxServerTTS, ChatterboxServerTTSOpenAI


def create_stt_service():
    """Crea y configura el servicio de Speech-to-Text"""
    stt_service_provider = os.getenv("STT_SERVICE_PROVIDER", "WHISPER_STREAM")
    if stt_service_provider == "WHISPER":
        return WhisperSTTService(
            model="medium",
            device="cpu",
            compute_type="int8", 
            language="es",
        )
    elif stt_service_provider == "WHISPER_STREAM":
        ec2_host = os.getenv('EC2_HOST_WHISPER_STREAM', os.getenv('EC2_HOST'))
        if not ec2_host:
            raise ValueError("Must set EC2_HOST or EC2_HOST_WHISPER_STREAM")
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
    else:
        raise ValueError(f"Unknown STT_SERVICE_PROVIDER: {stt_service_provider}")


def create_tts_service(session: aiohttp.ClientSession):
    """Crea y configura el servicio de Text-to-Speech"""
    tts_service_provider = os.getenv("TTS_SERVICE_PROVIDER", "CHATTERBOX_SERVER")
    if tts_service_provider == "CHATTERBOX_SERVER":
        ec2_host = os.getenv('EC2_HOST_CHATTERBOX', os.getenv('EC2_HOST'))
        if not ec2_host:
            raise ValueError("Must set EC2_HOST or EC2_HOST_CHATTERBOX")
        return ChatterboxServerTTS(
            aiohttp_session=session,
            base_url=f"http://{ec2_host}:{os.getenv('EC2_CHATTERBOX_PORT', 8004)}",
            voice="Elena.wav",
            chunk_size=120
        )
    elif tts_service_provider == "CHATTERBOX_SERVER_OPENAI":
        ec2_host = os.getenv('EC2_HOST_CHATTERBOX', os.getenv('EC2_HOST'))
        if not ec2_host:
            raise ValueError("Must set EC2_HOST or EC2_HOST_CHATTERBOX")
        return ChatterboxServerTTSOpenAI(
            aiohttp_session=session,
            base_url=f"http://{ec2_host}:{os.getenv('EC2_CHATTERBOX_PORT', 8004)}",
            voice="Emily.wav",
        )
    elif tts_service_provider == "PIPER":
        ec2_host = os.getenv('EC2_HOST_PIPER', os.getenv('EC2_HOST'))
        if not ec2_host:
            raise ValueError("Must set EC2_HOST or EC2_HOST_PIPER")
        return PiperTTSService(
            base_url=f"http://{ec2_host}:{os.getenv('EC2_PIPER_PORT', 5002)}",
            aiohttp_session=session,
        )
    elif tts_service_provider == "POLLY":
        return PollyTTSService(
            voice="Lupe",
            speech_engine="generative",
            language="es-US"
        )
    elif tts_service_provider == "ELEVENLABS":
        return ElevenLabsTTSService(
            api_key=os.getenv("ELEVENLABS_API_KEY")
        )
    else:
        raise ValueError(f"Unknown TTS_SERVICE_PROVIDER: {tts_service_provider}")


def create_llm_service():
    """Crea y configura el servicio de LLM (AWS Bedrock)"""
    return AWSBedrockLLMService(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id")),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key")),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token")),
        region=os.getenv("AWS_DEFAULT_REGION", os.getenv("aws_default_region", "us-east-1")),
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
