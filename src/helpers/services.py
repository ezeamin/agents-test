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
from pipecat.services.piper.tts import PiperTTSService

log = logging.getLogger(__name__)

# Tamaño de chunk de audio para Pipecat (bytes de PCM)
TTS_CHUNK_SIZE = 300#4096


class ChatterboxTTSService(TTSService):
    """TTS que usa la API de Chatterbox: POST /tts con JSON (no compatible con OpenAI)."""

    def __init__(
        self,
        *,
        base_url: str,
        voice_mode: str = "predefined",
        predefined_voice_id: str = "Elena.wav",
        reference_audio_filename: str = "",
        language: str = "es",
        output_format: str = "wav",
        split_text: bool = True,
        chunk_size: int = 240,
        temperature: float = 0.8,
        exaggeration: float = 1.3,
        cfg_weight: float = 0.5,
        speed_factor: float = 1.0,
        seed: int | None = 1775,
        timeout: float = 30.0,
        sample_rate: int = 24000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._base_url = base_url.rstrip("/")
        self._voice_mode = (voice_mode or "predefined").lower()
        # predefined_voice_id debe incluir .wav (ej. Elena.wav) según la API que funciona
        pvid = (predefined_voice_id or "Elena.wav").strip()
        self._predefined_voice_id = pvid if pvid.lower().endswith(".wav") else f"{pvid}.wav"
        self._reference_audio_filename = reference_audio_filename or (
            "Juanma.wav" if self._voice_mode == "clone" else "Elena.wav"
        )
        self._language = language
        self._output_format = output_format
        self._split_text = split_text
        self._chunk_size = chunk_size
        self._temperature = temperature
        self._exaggeration = exaggeration
        self._cfg_weight = cfg_weight
        self._speed_factor = speed_factor
        self._seed = seed
        self._timeout = timeout

    async def run_tts(self, text: str):
        """Genera audio llamando a POST {base_url}/tts con el JSON de Chatterbox."""
        log.debug("%s: Generating TTS [%s]", self, text[:50] + "..." if len(text) > 50 else text)
        try:
            url = f"{self._base_url}/tts"
            payload = {
                "text": text,
                "voice_mode": self._voice_mode,
                "output_format": self._output_format,
                "split_text": self._split_text,
                "chunk_size": self._chunk_size,
                "temperature": self._temperature,
                "exaggeration": self._exaggeration,
                "cfg_weight": self._cfg_weight,
                "speed_factor": self._speed_factor,
                "language": self._language,
            }
            if self._seed is not None:
                payload["seed"] = self._seed
            if self._voice_mode == "predefined":
                payload["predefined_voice_id"] = self._predefined_voice_id
            else:
                # clone: servidor usa reference_audio_filename (ej. Juanma.wav)
                payload["reference_audio_filename"] = self._reference_audio_filename
            print("Sending payload to Chatterbox TTS: %s", payload)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                yield ErrorFrame(error=f"Chatterbox TTS error: {resp.status_code} {resp.text[:200]}")
                return
            wav_bytes = resp.content
            if not wav_bytes:
                yield ErrorFrame(error="Chatterbox TTS: respuesta vacía")
                return
            # Si la respuesta es JSON (ej. {"audio": "base64..."}), extraer el audio
            content_type = (resp.headers.get("content-type") or "").lower()
            if "application/json" in content_type:
                try:
                    data = resp.json()
                    wav_bytes = base64.b64decode(data.get("audio") or data.get("content") or data.get("data") or "")
                except Exception as e:
                    yield ErrorFrame(error=f"Chatterbox TTS: no se pudo leer audio JSON: {e}")
                    return
            yield TTSStartedFrame()
            # Decodificar WAV a PCM (sample_rate, canales) y emitir en chunks
            with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
                sr = wav.getframerate()
                nch = wav.getnchannels()
                pcm = wav.readframes(wav.getnframes())
            for i in range(0, len(pcm), TTS_CHUNK_SIZE):
                chunk = pcm[i : i + TTS_CHUNK_SIZE]
                if chunk:
                    yield TTSAudioRawFrame(chunk, sr, nch)
            yield TTSStoppedFrame()
        except httpx.TimeoutException as e:
            log.error("Chatterbox TTS timeout: %s", e)
            yield ErrorFrame(error=f"Chatterbox TTS: Request timed out ({self._timeout}s)")
        except Exception as e:
            log.exception("Chatterbox TTS error")
            yield ErrorFrame(error=f"Chatterbox TTS: {e!s}")

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
    stt_service_provider = os.getenv("STT_SERVICE_PROVIDER", "WHISPER")
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
    tts_service_provider = os.getenv("TTS_SERVICE_PROVIDER", "PIPER")
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
        # Chatterbox: voice_mode=predefined (voces en voices/) o clone (audio de referencia, ej. Juanma.wav)
        base_url = os.getenv(
            "TTS_BASE_URL",
            "http://ec2-18-191-66-251.us-east-2.compute.amazonaws.com:8004",
        ).rstrip("/").replace("/v1", "")
        voice_mode = os.getenv("TTS_VOICE_MODE", "predefined").lower()
        seed_env = os.getenv("TTS_SEED", "1775")
        seed = int(seed_env) if seed_env.strip() else None
        if seed == 0:
            seed = 1775
        # Valores por defecto alineados con el POST que funciona en el servidor (Elena.wav, temperature 0.8, etc.)
        split_text = os.getenv("TTS_SPLIT_TEXT", "true").lower() in ("1", "true", "yes")
        return ChatterboxTTSService(
            base_url=base_url,
            voice_mode=voice_mode,
            predefined_voice_id=os.getenv("TTS_PREDEFINED_VOICE_ID", "Elena.wav"),
            reference_audio_filename=os.getenv("TTS_REFERENCE_AUDIO", "Juanma.wav" if voice_mode == "clone" else "Elena.wav"),
            language=os.getenv("TTS_LANGUAGE", "es"),
            output_format=os.getenv("TTS_OUTPUT_FORMAT", "wav"),
            split_text=split_text,
            chunk_size=int(os.getenv("TTS_CHUNK_SIZE", "240")),
            temperature=float(os.getenv("TTS_TEMPERATURE", "0.8")),
            exaggeration=float(os.getenv("TTS_EXAGGERATION", "1.0")),
            cfg_weight=float(os.getenv("TTS_CFG_WEIGHT", "0.5")),
            speed_factor=float(os.getenv("TTS_SPEED_FACTOR", "1")),
            seed=seed,
            timeout=float(os.getenv("TTS_TIMEOUT", "60")),
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