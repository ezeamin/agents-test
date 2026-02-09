import asyncio
import websockets
import sounddevice as sd
import numpy as np

WS_URL = "ws://ec2-3-133-89-61.us-east-2.compute.amazonaws.com:8000/asr"

RATE = 16000
BLOCK = 1025

async def main():
    async with websockets.connect(WS_URL, max_size=None) as ws:
        print("Connected to STT server")

        def callback(indata, frames, time, status):
            if status:
                print("Audio status:", status)

            # Convert float32 -> int16 PCM (s16le)
            pcm = (indata * 32767).astype(np.int16)

            # Send raw bytes
            asyncio.run_coroutine_threadsafe(
                ws.send(pcm.tobytes()),
                loop
            )

        with sd.InputStream(
            samplerate=RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK,
            callback=callback
        ):
            while True:
                msg = await ws.recv()
                print(">>", msg)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())