#!/usr/bin/env python3
"""
Standalone test for ChatterboxServerTTS custom integration.

Synthesizes text and plays the audio, logging chunk timing to help diagnose
clipping / latency issues independently of the full Pipecat pipeline.

Usage:
    # Interactive mode — type text, hear it:
    python test_chatterbox_custom_integration.py

    # Synthesize one string:
    python test_chatterbox_custom_integration.py "Hola, soy Nova"

    # Override inference params:
    python test_chatterbox_custom_integration.py --voice Elena.wav --temp 0.5 --exag 1.0

    # Save output to WAV:
    python test_chatterbox_custom_integration.py --save output.wav "Hola"

    # Stream audio as chunks arrive (vs buffering all first):
    python test_chatterbox_custom_integration.py --stream
"""

import asyncio
import argparse
import sys
import time
import wave
from pathlib import Path

import aiohttp
import numpy as np
import sounddevice as sd

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from helpers.chatterbox_custom_integration import ChatterboxServerTTS, ChatterboxServerTTSSentenceSplit
from pipecat.frames.frames import AudioRawFrame, ErrorFrame, TTSStartedFrame, TTSStoppedFrame

# ── default parameters (edit here or override via CLI args) ───────────────────
DEFAULT_URL         = "http://localhost:8004"
DEFAULT_VOICE       = "Robert.wav"
DEFAULT_LANGUAGE    = "es"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_EXAGGERATION = 1.3
DEFAULT_CFG_WEIGHT  = 0.5
DEFAULT_SPEED       = 1.0
DEFAULT_SEED        = 2024
DEFAULT_CHUNK_SIZE  = None  # set to e.g. 100 to enable server-side split_text

DEFAULT_TEXT = (
    "Hola, soy Nova, tu asistente de Strata Sportiva. "
    "¿En qué puedo ayudarte hoy?"
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _pcm_to_float(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


async def synthesize(
    tts: ChatterboxServerTTS,
    text: str,
    *,
    stream: bool = False,
    save_path: str | None = None,
) -> None:
    """Run TTS, play audio, and print timing diagnostics."""
    print(f"\nText: {text!r}")

    chunks: list[bytes] = []
    chunk_times: list[float] = []
    t0 = time.perf_counter()
    out_stream: sd.OutputStream | None = None

    sample_rate: int = tts.sample_rate

    if stream:
        out_stream = sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32")
        out_stream.start()

    async for frame in tts.run_tts(text, context_id="test"):
        if isinstance(frame, TTSStartedFrame):
            print(f"  → TTS started")

        elif isinstance(frame, TTSStoppedFrame):
            elapsed = time.perf_counter() - t0
            print(f"  → TTS stopped  [{elapsed:.2f}s total inference]")

        elif isinstance(frame, AudioRawFrame):
            elapsed = time.perf_counter() - t0
            chunks.append(frame.audio)
            chunk_times.append(elapsed)
            if len(chunks) == 1:
                print(f"  → First chunk  [TTFA {elapsed:.2f}s]")
            if stream and out_stream is not None:
                out_stream.write(_pcm_to_float(frame.audio))

        elif isinstance(frame, ErrorFrame):
            print(f"  [ERROR] {frame.error}")
            if out_stream:
                out_stream.stop()
                out_stream.close()
            return

    if out_stream:
        out_stream.stop()
        out_stream.close()

    if not chunks:
        print("  No audio received.")
        return

    audio_bytes = b"".join(chunks)
    total_audio_s = len(audio_bytes) / (sample_rate * 2)
    print(f"  Chunks: {len(chunks)}  |  Audio duration: {total_audio_s:.2f}s")

    # Gap analysis — helps distinguish server-side pauses from playback glitches
    if len(chunk_times) > 1:
        gaps = [chunk_times[i] - chunk_times[i - 1] for i in range(1, len(chunk_times))]
        max_gap = max(gaps)
        large_gaps = [(i, g) for i, g in enumerate(gaps) if g > 0.15]
        print(f"  Max inter-chunk gap: {max_gap * 1000:.0f}ms", end="")
        if large_gaps:
            print(f"  |  Gaps >150ms: {len(large_gaps)}")
            for idx, g in large_gaps[:5]:
                print(f"    after chunk {idx}: {g * 1000:.0f}ms")
        else:
            print()

    if save_path:
        with wave.open(save_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)
        print(f"  Saved → {save_path}")

    if not stream:
        audio_np = _pcm_to_float(audio_bytes)
        print(f"\nPlaying {total_audio_s:.2f}s...")
        sd.play(audio_np, samplerate=sample_rate)
        sd.wait()

    print("Done.")


# ── main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="Test ChatterboxServerTTS")
    parser.add_argument("text", nargs="*", help="Text to synthesize (interactive mode if omitted)")
    parser.add_argument("--url",   default=DEFAULT_URL,         help="Chatterbox server base URL")
    parser.add_argument("--voice", default=DEFAULT_VOICE,       help="Voice filename (e.g. Elena.wav)")
    parser.add_argument("--lang",  default=DEFAULT_LANGUAGE,    help="Language code")
    parser.add_argument("--temp",  type=float, default=DEFAULT_TEMPERATURE,  metavar="F", help="Temperature 0.0–1.0")
    parser.add_argument("--exag",  type=float, default=DEFAULT_EXAGGERATION, metavar="F", help="Exaggeration 1.0–2.0")
    parser.add_argument("--cfg",   type=float, default=DEFAULT_CFG_WEIGHT,   metavar="F", help="CFG weight 0.0–1.0")
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED,        metavar="F", help="Speed factor 0.5–2.0")
    parser.add_argument("--seed",  type=int,   default=DEFAULT_SEED,         help="RNG seed (None = random)")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, metavar="N",
                        help="Enable split_text with this chunk size (chars)")
    parser.add_argument("--stream", action="store_true",
                        help="Play audio chunks as they arrive instead of buffering")
    parser.add_argument("--save",  metavar="FILE", help="Save output to WAV file")
    args = parser.parse_args()

    async with aiohttp.ClientSession() as session:
        tts = ChatterboxServerTTS(
            aiohttp_session=session,
            base_url=args.url,
            voice=args.voice,
            language=args.lang,
            temperature=args.temp,
            exaggeration=args.exag,
            cfg_weight=args.cfg,
            speed_factor=args.speed,
            seed=args.seed,
            chunk_size=args.chunk_size
        )
        # Pipecat stores the constructor sample_rate in _init_sample_rate but only
        # populates _sample_rate (what .sample_rate returns) from StartFrame during
        # pipeline startup. Set it directly so run_tts() can create AudioRawFrames.
        tts._sample_rate = tts._init_sample_rate
        await tts._fetch_voice_mode()

        header = (
            f"Server: {args.url}  Voice: {args.voice}  "
            f"Temp: {args.temp}  Exag: {args.exag}  CFG: {args.cfg}  "
            f"Speed: {args.speed}  Seed: {args.seed}"
        )
        if args.chunk_size:
            header += f"  ChunkSize: {args.chunk_size}"
        if args.stream:
            header += "  [streaming playback]"
        print(header)

        if args.text:
            await synthesize(
                tts, " ".join(args.text),
                stream=args.stream,
                save_path=args.save,
            )
        else:
            print("\nInteractive mode. Press Ctrl+C to exit.")
            save_counter = 0
            while True:
                try:
                    text = input("\nText> ").strip()
                    if not text:
                        continue
                    save_path = None
                    if args.save:
                        save_counter += 1
                        p = Path(args.save)
                        save_path = str(p.with_stem(f"{p.stem}_{save_counter}"))
                    await synthesize(tts, text, stream=args.stream, save_path=save_path)
                except (KeyboardInterrupt, EOFError):
                    print("\nExiting.")
                    break


if __name__ == "__main__":
    asyncio.run(main())
