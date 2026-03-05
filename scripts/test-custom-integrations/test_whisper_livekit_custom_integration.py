#!/usr/bin/env python3
"""
Standalone test for WhisperLiveKitSTT custom integration.

Streams mic audio to the WhisperLiveKit server and prints transcriptions,
bypassing the Pipecat pipeline so you can rule out pipeline-level issues.

Shows when audio is SENT vs when transcripts ARRIVE to help pinpoint
whether truncation happens in the WebSocket receive loop or on the server.

Usage:
    # Default (connects to localhost:8000):
    python test_whisper_livekit_custom_integration.py

    # Override server URL and mic block size:
    python test_whisper_livekit_custom_integration.py --url ws://myserver:8000/asr --block 3200

    # Send audio in larger batches (matches pipeline behavior more closely):
    python test_whisper_livekit_custom_integration.py --block 6400

    # Show raw server messages (before parsing):
    python test_whisper_livekit_custom_integration.py --raw
"""

import asyncio
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import websockets

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from helpers.whisper_livekit_custom_integration import WhisperLiveKitSTT
from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame

# ── default parameters (edit here or override via CLI args) ───────────────────
DEFAULT_URL        = "ws://localhost:8000/asr"
DEFAULT_RATE       = 16000   # must match server expectation
DEFAULT_BLOCK      = 1600    # samples per mic callback (100ms at 16kHz)


# ── testable subclass ─────────────────────────────────────────────────────────

class TestableSTT(WhisperLiveKitSTT):
    """
    WhisperLiveKitSTT with:
    - Pipecat pipeline init bypassed (no FrameProcessor/STTService needed)
    - push_frame() replaced with an asyncio queue so frames can be consumed
      in the main task without a running pipeline

    All WebSocket logic (_recv_loop, run_stt, _close, _flush) is inherited
    unchanged from WhisperLiveKitSTT, so this tests the real class code.
    """

    def __init__(self, url: str, sample_rate: int = 16000, show_raw: bool = False):
        # Bypass Pipecat FrameProcessor.__init__ — only set what the parent
        # methods actually use: url, ws, recv_task, closed, _lines_seen,
        # and sample_rate (exposed via property below).
        self.url = url
        self._sample_rate = sample_rate
        self.ws = None
        self.recv_task = None
        self.closed = False
        self._lines_seen = 0
        self._frame_queue: asyncio.Queue = asyncio.Queue()
        self._show_raw = show_raw

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    async def push_frame(self, frame, *_) -> None:  # noqa: ANN002
        """Capture frames to a local queue instead of forwarding downstream."""
        await self._frame_queue.put(frame)

    # ── raw message hook (optional diagnostics) ──────────────────────────────

    async def _recv_loop(self):
        """Identical to parent, but optionally prints raw server messages."""
        try:
            async for msg in self.ws:
                if self._show_raw:
                    print(f"  [raw] {msg}")
                data = json.loads(msg)
                msg_type = data.get("type", "")
                if msg_type in ("config", "ready_to_stop"):
                    continue

                interim = data.get("buffer_transcription", "")
                lines = data.get("lines", [])

                from pipecat.utils.time import time_now_iso8601

                if interim:
                    await self.push_frame(
                        InterimTranscriptionFrame(
                            text=interim,
                            user_id="",
                            timestamp=time_now_iso8601(),
                        )
                    )

                if lines:
                    if len(lines) < self._lines_seen:
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
            print(f"[recv_loop error] {e}")

    # ── lifecycle (no StartFrame / FrameProcessor needed) ────────────────────

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.url, max_size=None)
        self.closed = False
        self.recv_task = asyncio.create_task(self._recv_loop())
        print(f"Connected → {self.url}")

    async def disconnect(self) -> None:
        await self._flush()
        await self._close()
        print("Disconnected.")


# ── frame printer ─────────────────────────────────────────────────────────────

async def print_frames(stt: TestableSTT) -> None:
    while True:
        frame = await stt._frame_queue.get()
        ts = time.strftime("%H:%M:%S")
        if isinstance(frame, InterimTranscriptionFrame):
            print(f"  [{ts}] interim → {frame.text}")
        elif isinstance(frame, TranscriptionFrame):
            print(f"  [{ts}] FINAL   → {frame.text}")


# ── main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="Test WhisperLiveKitSTT")
    parser.add_argument("--url",   default=DEFAULT_URL,  help="WebSocket URL of WhisperLiveKit server")
    parser.add_argument("--rate",  type=int, default=DEFAULT_RATE,  metavar="HZ",
                        help="Mic sample rate in Hz (must match server, default 16000)")
    parser.add_argument("--block", type=int, default=DEFAULT_BLOCK, metavar="N",
                        help="Mic block size in samples (default 1600 = 100ms at 16kHz). "
                             "Increase to send larger batches, closer to pipeline behavior.")
    parser.add_argument("--raw",   action="store_true",
                        help="Print raw JSON messages from the server before parsing")
    args = parser.parse_args()

    stt = TestableSTT(url=args.url, sample_rate=args.rate, show_raw=args.raw)
    await stt.connect()

    loop = asyncio.get_event_loop()
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
    bytes_sent = 0
    send_count = 0

    def mic_callback(indata, frames, time_info, status):
        if status:
            print(f"  [mic] {status}")
        pcm = (indata[:, 0] * 32767).astype(np.int16)
        asyncio.run_coroutine_threadsafe(audio_queue.put(pcm.tobytes()), loop)

    block_ms = int(args.block / args.rate * 1000)
    print(
        f"Mic: {args.rate} Hz  Block: {args.block} samples ({block_ms}ms)\n"
        f"Listening... Ctrl+C to stop.\n"
    )

    printer = asyncio.create_task(print_frames(stt))

    with sd.InputStream(
        samplerate=args.rate,
        channels=1,
        dtype="float32",
        blocksize=args.block,
        callback=mic_callback,
    ):
        try:
            while True:
                audio = await audio_queue.get()
                send_count += 1
                bytes_sent += len(audio)
                # run_stt sends the audio in 100ms sub-chunks via the WebSocket
                # (matching exactly what the Pipecat pipeline does)
                async for _ in stt.run_stt(audio):
                    pass  # transcripts arrive via _recv_loop → push_frame
        except KeyboardInterrupt:
            print(f"\nStopping. Sent {send_count} blocks ({bytes_sent / 1024:.1f} KB total).")

    printer.cancel()
    await stt.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
