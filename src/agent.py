"""Agente de voz con pipeline STT -> LLM -> TTS"""
import argparse
from contextlib import asynccontextmanager

import aiohttp
import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from helpers import (
    SYSTEM_MESSAGE,
    tools_list,
    tools_schema,
    create_stt_service,
    create_tts_service,
    create_llm_service,
)
from helpers.config import ICE_SERVERS


async def run_bot(webrtc_connection: SmallWebRTCConnection):
    """Configura y ejecuta el bot de voz para una conexión WebRTC."""
    print("Starting bot")

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
        ),
    )

    async with aiohttp.ClientSession() as session:
        stt = create_stt_service()
        tts = create_tts_service(session)
        llm = create_llm_service()

        for tool in tools_list:
            llm.register_direct_function(handler=tool, cancel_on_interruption=True)
        messages = [{"role": "system", "content": SYSTEM_MESSAGE}]
        context = LLMContext(messages, tools=tools_schema)

        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                user_turn_strategies=UserTurnStrategies(
                    stop=[
                        TurnAnalyzerUserTurnStopStrategy(
                            turn_analyzer=LocalSmartTurnAnalyzerV3()
                        )
                    ]
                )
            ),
        )

        pipeline = Pipeline([
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[MetricsLogObserver()],
            enable_turn_tracking=True,
            idle_timeout_secs=300,
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            print("Client connected")
            messages.append(
                {"role": "system", "content": "Presentate brevemente al usuario."}
            )
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            print("Client disconnected")
            await task.cancel()

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)


# --- HTTP / WebRTC Server ---

_handler: SmallWebRTCRequestHandler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _handler
    _handler = SmallWebRTCRequestHandler(
        ice_servers=[IceServer(urls=ICE_SERVERS)]
    )
    yield
    await _handler.close()


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


@app.get("/")
async def serve_index():
    return FileResponse("src/client.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nova Voice Agent")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
