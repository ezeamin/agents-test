import asyncio
import re
from typing import AsyncGenerator, Dict, Optional

import aiohttp
from loguru import logger

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    StartFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService

"""
IMPORTANT:

Why your experiment #1 (OpenAITTSService with custom base_url) will likely fail and did not when using Livekit

1) VALID_VOICES mapping — Pipecat does VALID_VOICES[self._voice_id] which is a hardcoded dict of OpenAI voices (alloy, ash, coral, etc.). Passing "Emily.wav" will raise KeyError. Your original had voice="" which would also crash.

2) response_format: "pcm" — Pipecat's OpenAI plugin requests raw PCM format. Your Chatterbox server likely only supports wav and opus, so it would fail even if the voice issue were bypassed.

The Livekit openai.TTS plugin worked because it's a different, simpler implementation that doesn't have these restrictions — it just passes the voice string and format directly to the HTTP request.
"""

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _split_sentences(text: str) -> list:
    """Split text into sentences on [.!?] followed by whitespace."""
    parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return parts or [text]


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
    """DEPRECATED — use ChatterboxServerTTSPipelined instead.

    This approach splits the LLM response into sentences client-side and fires
    one sequential /tts request per sentence. In practice it added more latency
    than it saved because pipecat's base class still awaits each run_tts
    generator fully before moving to the next sentence, so requests are never
    truly concurrent.

    ChatterboxServerTTSPipelined solves the same problem at the asyncio level
    by firing all requests as background tasks and playing them back in order.
    """

    async def run_tts(self, text: str, context_id: str):
        logger.debug(f"Running TTS on text: {text}")
        sentences = _split_sentences(text)

        yield TTSStartedFrame(context_id=context_id)
        for sentence in sentences:
            logger.debug(f"Running TTS on sentence: {sentence}")
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


class ChatterboxServerTTSPipelined(TTSService):
    """Pipelined Chatterbox TTS: fires one /tts HTTP request per sentence immediately,
    without waiting for previous sentences to finish generating.

    Each sentence gets its own asyncio.Queue (audio context). A background task
    drains these queues in order so audio always plays sentence-by-sentence, but
    sentence N+1 is already being generated by the server while sentence N is playing.

    This eliminates the inter-sentence gap caused by the base class awaiting the
    full run_tts generator before moving to the next sentence.
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
        self._voice_mode = "predefined"
        self._voice_id = voice
        self._contexts: Dict[str, asyncio.Queue] = {}
        self._contexts_queue: asyncio.Queue = asyncio.Queue()
        self._audio_task: Optional[asyncio.Task] = None

    async def start(self, frame: StartFrame):
        await super().start(frame)
        await self._fetch_voice_mode()
        self._contexts_queue = asyncio.Queue()
        self._contexts = {}
        self._audio_task = asyncio.create_task(self._audio_context_handler())

    async def stop(self, frame: EndFrame):
        await super().stop(frame)
        await self._contexts_queue.put(None)
        if self._audio_task:
            await self._audio_task
            self._audio_task = None

    async def cancel(self, frame: CancelFrame):
        await super().cancel(frame)
        if self._audio_task:
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass
            self._audio_task = None
        self._contexts_queue = asyncio.Queue()
        self._contexts = {}

    async def _fetch_voice_mode(self):
        try:
            async with self._session.get(f"{self._base_url}/get_predefined_voices") as resp:
                if resp.status == 200:
                    voices = await resp.json()
                    filenames = {v.get("filename") for v in voices}
                    voice = self._voice_id
                    if not voice.lower().endswith(".wav"):
                        voice = f"{voice}.wav"
                    self._voice_mode = "predefined" if voice in filenames else "clone"
                    logger.info(f"Chatterbox voice_mode for '{self._voice_id}': {self._voice_mode}")
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

        # Register context queue before launching the request so the audio
        # handler can start waiting for its frames in arrival order.
        self._contexts[context_id] = asyncio.Queue()
        await self._contexts_queue.put(context_id)

        yield TTSStartedFrame(context_id=context_id)

        # Fire the HTTP request as a background task — don't await it.
        # pipecat will immediately call run_tts for the next sentence.
        asyncio.create_task(self._fetch_and_fill(text, context_id, voice))

        # Yielding None signals process_generator to finish this generator
        # immediately so the pipeline moves on to the next sentence.
        yield None

    async def _fetch_and_fill(self, text: str, context_id: str, voice: str):
        """Makes the /tts HTTP request and places audio into the context queue."""
        queue = self._contexts.get(context_id)
        if queue is None:
            return

        payload = {
            "text": text,
            "voice_mode": self._voice_mode,
            "predefined_voice_id": voice,
            "output_format": "wav",
            "language": self._language,
            "temperature": self._temperature,
            "exaggeration": self._exaggeration,
            "cfg_weight": self._cfg_weight,
            "speed_factor": self._speed_factor,
        }
        if self._voice_mode == "clone":
            payload["reference_audio_filename"] = voice
        if self._seed is not None:
            payload["seed"] = self._seed

        try:
            async with self._session.post(f"{self._base_url}/tts", json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Chatterbox /tts error {resp.status}: {body[:200]}")
                    await queue.put(ErrorFrame(error=f"Chatterbox /tts error {resp.status}: {body[:200]}"))
                    return

                audio_bytes = await resp.read()
                # Strip the 44-byte WAV header to get raw PCM
                pcm = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
                if pcm:
                    await queue.put(
                        TTSAudioRawFrame(
                            audio=pcm,
                            sample_rate=self.sample_rate,
                            num_channels=1,
                            context_id=context_id,
                        )
                    )
        except Exception as e:
            logger.error(f"Chatterbox /tts error: {e}")
            await queue.put(ErrorFrame(error=f"Chatterbox /tts error: {e}"))
        finally:
            await queue.put(None)  # sentinel: this context is done

    async def _audio_context_handler(self):
        """Drains context queues in order, pushing frames downstream."""
        while True:
            context_id = await self._contexts_queue.get()
            if context_id is None:
                break

            queue = self._contexts.get(context_id)
            if queue is None:
                continue

            try:
                while True:
                    frame = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if frame is None:
                        break
                    await self.push_frame(frame)
            except asyncio.TimeoutError:
                logger.warning(f"Chatterbox: timeout waiting for audio context {context_id}")
            except asyncio.CancelledError:
                raise
            finally:
                self._contexts.pop(context_id, None)

            await self.push_frame(TTSStoppedFrame(context_id=context_id))


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
