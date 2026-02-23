"""HTTP / WebRTC server — Nova Voice Agent"""
import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from helpers.config import ICE_SERVERS
from pipelines import _debug, run_bot


# ─── WebRTC handler ───────────────────────────────────────────────────────────

_handler: SmallWebRTCRequestHandler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _handler
    _handler = SmallWebRTCRequestHandler(
        ice_servers=[IceServer(urls=ICE_SERVERS)]
    )
    yield
    await _handler.close()


# ─── Routes ───────────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)


@app.post("/api/offer")
async def offer(request: SmallWebRTCRequest, background_tasks: BackgroundTasks):
    async def on_connection(connection: SmallWebRTCConnection):
        background_tasks.add_task(run_bot, connection)

    return await _handler.handle_web_request(
        request=request,
        webrtc_connection_callback=on_connection,
    )


@app.patch("/api/offer")
async def ice_candidate(request: SmallWebRTCPatchRequest):
    await _handler.handle_patch_request(request)
    return {"status": "success"}


@app.websocket("/ws/debug")
async def debug_ws(websocket: WebSocket):
    """Streams pipeline debug events (STT, LLM, TTS) to the frontend."""
    await _debug.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive; client sends nothing
    except WebSocketDisconnect:
        _debug.disconnect(websocket)


@app.get("/")
async def serve_index():
    return FileResponse("src/frontend/index.html")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nova Voice Agent")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
