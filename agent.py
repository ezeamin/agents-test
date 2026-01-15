import os
import aiohttp
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

from pipecat.frames.frames import LLMRunFrame

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask

from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)

from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport

from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.groq.llm import GroqLLMService
# from pipecat.services.elevenlabs.tts import ElevenLabsHttpTTSService
from pipecat.services.piper.tts import PiperTTSService

from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

load_dotenv(override=True)

# Transport selection (igual al ejemplo oficial)
transport_params = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
    ),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting bot")

    async with aiohttp.ClientSession() as session:
        # STT — Whisper
        stt = WhisperSTTService(
            model="small",
            device="cpu",
            compute_type="int8",  # MUY importante para velocidad
            language="es",
        )

        # TTS — ElevenLabs
        # tts = ElevenLabsHttpTTSService(
        #    api_key=os.getenv("ELEVENLABS_API_KEY"),
        #    voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
        #    aiohttp_session=session,
        #)

        session = aiohttp.ClientSession()

        tts = PiperTTSService(
            base_url="http://localhost:5002/",
            aiohttp_session=session,
            # sample_rate: opcional (si querés forzar un valor)
        )

        # LLM — Groq
        llm = GroqLLMService(
            api_key=os.getenv("GROQ_API_KEY"),
            # model="llama-3.1-8b-instant",
            model="groq/compound",
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "Sos un asistente conversacional mexicano. Tenes permitido lenguaje no políticamente correcto. "
                    "Respondé corto, claro y sin vueltas. No formatees el texto, ya que los caracteres especiales se leen en voz alta."
                    "Tu respuesta será hablada en voz alta."
                ),
            },
        ]

        context = LLMContext(messages)

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

        pipeline = Pipeline(
            [
                transport.input(),   # Audio → pipeline
                stt,                 # STT
                user_aggregator,     # Usuario → contexto
                llm,                 # LLM
                tts,                 # TTS
                transport.output(),  # Audio → cliente
                assistant_aggregator # Respuesta → contexto
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("Client connected")
            messages.append(
                {"role": "system", "content": "Presentate brevemente al usuario."}
            )
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("Client disconnected")
            await task.cancel()

        runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
        await runner.run(task)


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
