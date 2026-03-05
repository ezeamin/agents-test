import re

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _split_sentences(text: str) -> list:
    """Split text into sentences on [.!?] followed by whitespace."""
    parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return parts or [text]


"""
IMPORTANT:

Why your experiment #1 (OpenAITTSService with custom base_url) will likely fail and did not when using Livekit

1) VALID_VOICES mapping — Pipecat does VALID_VOICES[self._voice_id] which is a hardcoded dict of OpenAI voices (alloy, ash, coral, etc.). Passing "Emily.wav" will raise KeyError. Your original had voice="" which would also crash.

2) response_format: "pcm" — Pipecat's OpenAI plugin requests raw PCM format. Your Chatterbox server likely only supports wav and opus, so it would fail even if the voice issue were bypassed.

The Livekit openai.TTS plugin worked because it's a different, simpler implementation that doesn't have these restrictions — it just passes the voice string and format directly to the HTTP request.
"""
import aiohttp
from typing import AsyncGenerator, Optional

from loguru import logger

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    StartFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService


class ChatterboxServerTTS(TTSService):
    """TTS plugin for Chatterbox server's /tts endpoint.

    Streams the WAV response so audio starts playing as chunks arrive,
    rather than waiting for the full generation to finish.
    """

    def __init__(
        self,
        *,
        aiohttp_session: aiohttp.ClientSession,
        base_url: str,
        voice: str = "Elena.wav",
        language: str = "es",
        temperature: float = 0.1,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        speed_factor: float = 1.0,
        seed: Optional[int] = 1775,
        chunk_size: Optional[int] = None,
        sample_rate: int = 24000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._session = aiohttp_session
        self._base_url = base_url.rstrip("/")
        self._language = language
        self._temperature = temperature
        self._exaggeration = exaggeration
        self._cfg_weight = cfg_weight
        self._speed_factor = speed_factor
        self._seed = seed
        self._chunk_size = chunk_size
        self._voice_mode = "predefined"
        self._voice_id = voice

    async def start(self, frame: StartFrame):
        await super().start(frame)
        await self._fetch_voice_mode()

    async def _fetch_voice_mode(self):
        """Query the server for predefined voices and set voice_mode accordingly."""
        try:
            async with self._session.get(
                f"{self._base_url}/get_predefined_voices"
            ) as resp:
                if resp.status == 200:
                    voices = await resp.json()
                    filenames = {v.get("filename") for v in voices}
                    voice = self._voice_id
                    if not voice.lower().endswith(".wav"):
                        voice = f"{voice}.wav"
                    self._voice_mode = "predefined" if voice in filenames else "clone"
                    logger.info(
                        f"Chatterbox voice_mode for '{self._voice_id}': {self._voice_mode}"
                    )
                else:
                    logger.warning(
                        f"Could not fetch predefined voices ({resp.status}), defaulting to 'predefined'"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch predefined voices: {e}, defaulting to 'predefined'")

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        voice = self._voice_id
        if not voice.lower().endswith(".wav"):
            voice = f"{voice}.wav"

        voice_mode = self._voice_mode

        payload = {
            "text": text,
            "voice_mode": voice_mode,
            "predefined_voice_id": voice,
            "output_format": "wav",
            "language": self._language,
            "temperature": self._temperature,
            "exaggeration": self._exaggeration,
            "cfg_weight": self._cfg_weight,
            "speed_factor": self._speed_factor
        }

        if voice_mode == "clone":
            payload["reference_audio_filename"] = voice
        if self._seed is not None:
            payload["seed"] = self._seed
        if self._chunk_size and self._chunk_size > 0:
            payload["split_text"] = True
            payload["chunk_size"] = self._chunk_size

        try:
            async with self._session.post(
                f"{self._base_url}/tts", json=payload
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Chatterbox /tts error {resp.status}: {body[:200]}")
                    yield ErrorFrame(
                        error=f"Chatterbox /tts error {resp.status}: {body[:200]}"
                    )
                    return

                yield TTSStartedFrame(context_id=context_id)
                async for frame in self._stream_audio_frames_from_iterator(
                    resp.content.iter_any(), strip_wav_header=True
                ):
                    yield frame
                yield TTSStoppedFrame(context_id=context_id)
        except Exception as e:
            logger.error(f"Chatterbox /tts error: {e}")
            yield ErrorFrame(error=f"Chatterbox /tts error: {e}")


class ChatterboxServerTTSSentenceSplit(ChatterboxServerTTS):
    """Like ChatterboxServerTTS but splits the text into sentences and calls the
    server once per sentence, yielding audio as each sentence is ready.

    This lets the agent start speaking the first sentence while the server is
    still generating the rest, reducing perceived latency without relying on
    server-side split_text (which causes inter-chunk noise and is slower for
    short texts).

    The Chatterbox server currently batches the entire generation before
    sending; true token-by-token streaming is tracked in an upstream PR —
    when that lands, this class can be removed.
    # TODO: upstream streaming PR — <PR_URL>
    """

    async def run_tts(self, text: str, context_id: str):
        sentences = _split_sentences(text)

        yield TTSStartedFrame(context_id=context_id)
        for sentence in sentences:
            # Delegate to the parent's payload-building + streaming logic but
            # suppress the TTSStartedFrame / TTSStoppedFrame it emits so that
            # the pipeline sees exactly one started/stopped pair per LLM turn.
            async for frame in super().run_tts(sentence, context_id):
                if isinstance(frame, (TTSStartedFrame, TTSStoppedFrame)):
                    continue
                if isinstance(frame, ErrorFrame):
                    yield frame
                    return
                yield frame
        yield TTSStoppedFrame(context_id=context_id)


class ChatterboxServerTTSOpenAI(TTSService):
    """TTS plugin for Chatterbox server's OpenAI-compatible /v1/audio/speech endpoint.

    Streams the WAV response so audio starts playing as chunks arrive.
    """

    def __init__(
        self,
        *,
        aiohttp_session: aiohttp.ClientSession,
        base_url: str,
        voice: str = "Emily.wav",
        model: str = "t3",
        sample_rate: int = 24000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._session = aiohttp_session
        self._base_url = base_url.rstrip("/")
        self._model = model
        self.set_voice(voice)
        self.set_model_name(model)

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        payload = {
            "model": self._model,
            "voice": self._voice_id,
            "input": text,
        }

        try:
            async with self._session.post(
                f"{self._base_url}/v1/audio/speech", json=payload
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(
                        f"Chatterbox OpenAI endpoint error {resp.status}: {body[:200]}"
                    )
                    yield ErrorFrame(
                        error=f"Chatterbox OpenAI endpoint error {resp.status}: {body[:200]}"
                    )
                    return

                yield TTSStartedFrame()
                async for frame in self._stream_audio_frames_from_iterator(
                    resp.content.iter_any(), strip_wav_header=True
                ):
                    yield frame
                yield TTSStoppedFrame()
        except Exception as e:
            logger.error(f"Chatterbox OpenAI endpoint error: {e}")
            yield ErrorFrame(error=f"Chatterbox OpenAI endpoint error: {e}")
