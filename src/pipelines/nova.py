"""Pipeline de voz: STT → LLM → TTS con debug broadcast."""
import asyncio
import json

import aiohttp
from fastapi import WebSocket
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMRunFrame,
    SystemFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from helpers import (
    SYSTEM_MESSAGE,
    create_llm_service,
    create_stt_service,
    create_tts_service,
    tools_list,
    tools_schema,
)


# ─── Debug broadcaster ────────────────────────────────────────────────────────

class DebugBroadcaster:
    """Broadcasts pipeline events to all connected /ws/debug WebSocket clients."""

    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def send(self, event_type: str, text: str = ""):
        if not self._clients:
            return
        data = json.dumps({"type": event_type, "text": text})
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead


_debug = DebugBroadcaster()


# ─── Debug frame capture ──────────────────────────────────────────────────────

class DebugFrameCapture(FrameProcessor):
    """Passthrough processor that broadcasts relevant frames to the debug UI.

    Place after STT to capture transcriptions, after LLM to capture text output,
    and after TTS to capture speaking start/stop events.
    """

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterimTranscriptionFrame):
            asyncio.create_task(_debug.send("stt_interim", frame.text))
        elif isinstance(frame, TranscriptionFrame):
            asyncio.create_task(_debug.send("stt_final", frame.text))
        elif isinstance(frame, LLMFullResponseStartFrame):
            asyncio.create_task(_debug.send("llm_start"))
        elif isinstance(frame, LLMFullResponseEndFrame):
            asyncio.create_task(_debug.send("llm_end"))
        elif isinstance(frame, TextFrame):
            # Only LLM text reaches here (TranscriptionFrame is handled above)
            asyncio.create_task(_debug.send("llm_text", frame.text))
        elif isinstance(frame, TTSStartedFrame):
            asyncio.create_task(_debug.send("tts_start"))
        elif isinstance(frame, TTSStoppedFrame):
            asyncio.create_task(_debug.send("tts_stop"))

        # super() handles SystemFrames (StartFrame, CancelFrame, etc.)
        # All other frames must be pushed manually
        if not isinstance(frame, SystemFrame):
            await self.push_frame(frame, direction)


# ─── Pipeline ─────────────────────────────────────────────────────────────────

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
            DebugFrameCapture(),       # captures STT transcription frames
            user_aggregator,
            llm,
            DebugFrameCapture(),       # captures LLM text + LLM start/end frames
            tts,
            DebugFrameCapture(),       # captures TTS start/stop frames
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
