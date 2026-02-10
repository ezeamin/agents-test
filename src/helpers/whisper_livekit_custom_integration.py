import asyncio
import json
import websockets
from typing import AsyncGenerator

from pipecat.services.stt_service import STTService
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    StartFrame,
    EndFrame,
    CancelFrame,
)
from pipecat.utils.time import time_now_iso8601


class WhisperLiveKitSTT(STTService):
    def __init__(self, url: str, sample_rate: int = 16000, **kwargs):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self.url = url
        self.ws = None
        self.recv_task = None
        self.closed = False
        self._lines_seen = 0

    # ---------- lifecycle ----------

    async def start(self, frame: StartFrame):
        await super().start(frame)
        self.ws = await websockets.connect(self.url, max_size=None)
        self.closed = False
        self.recv_task = asyncio.create_task(self._recv_loop())
        self.logger.info("WhisperLiveKit STT connected")

    async def stop(self, frame: EndFrame):
        await super().stop(frame)
        await self._flush()
        await self._close()

    async def cancel(self, frame: CancelFrame):
        await super().cancel(frame)
        await self._close()

    async def _close(self):
        if self.closed:
            return
        self.closed = True
        if self.recv_task:
            self.recv_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.logger.info("WhisperLiveKit STT closed")

    async def _flush(self):
        if self.ws:
            # empty frame = end of speech
            await self.ws.send(b"")

    # ---------- receive side ----------

    async def _recv_loop(self):
        try:
            async for msg in self.ws:
                data = json.loads(msg)

                # Skip control messages
                msg_type = data.get("type", "")
                if msg_type in ("config", "ready_to_stop"):
                    continue

                # WhisperLiveKit schema
                interim = data.get("buffer_transcription", "")
                lines = data.get("lines", [])

                if interim:
                    await self.push_frame(
                        InterimTranscriptionFrame(
                            text=interim,
                            user_id="",
                            timestamp=time_now_iso8601(),
                        )
                    )

                # Only emit NEW lines (lines array is cumulative)
                if lines:
                    if len(lines) < self._lines_seen:
                        # Server reset the lines (e.g. new utterance)
                        self._lines_seen = 0
                    if len(lines) > self._lines_seen:
                        new_lines = lines[self._lines_seen:]
                        self._lines_seen = len(lines)
                        final = " ".join(
                            l.get("text", "") for l in new_lines if l.get("text")
                        ).strip()
                        if final:
                            await self.push_frame(
                                TranscriptionFrame(
                                    text=final,
                                    user_id="",
                                    timestamp=time_now_iso8601(),
                                )
                            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"WhisperLiveKit recv loop error: {e}")

    # ---------- send side ----------

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        if not self.ws:
            return

        # send audio in 100ms chunks
        chunk_size = int(self.sample_rate * 0.1) * 2  # s16le
        for i in range(0, len(audio), chunk_size):
            await self.ws.send(audio[i : i + chunk_size])
            await asyncio.sleep(0)

        # Deepgram style: transcripts arrive via recv loop
        yield None
