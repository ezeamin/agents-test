"""HTTP / WebRTC server — Nova Voice Agent"""
import argparse
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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


# ─── Static files + SPA fallback ──────────────────────────────────────────────

_DIST_DIR = "src/frontend/dist"

# Serve Vite's hashed assets (JS, CSS, images) under /assets.
# Must be registered before the catch-all so these paths resolve to real files.
if os.path.isdir(f"{_DIST_DIR}/assets"):
    app.mount("/assets", StaticFiles(directory=f"{_DIST_DIR}/assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> FileResponse:
    """
    SPA catch-all: any path that didn't match an API or WebSocket route
    returns index.html so react-router-dom handles client-side navigation
    (/login, /callback, etc.).
    In local dev, run `bun dev` in src/frontend/ and use its proxy instead.
    """
    return FileResponse(f"{_DIST_DIR}/index.html")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nova Voice Agent")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
