"""Agente de voz con pipeline STT → LLM → TTS"""
import aiohttp

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
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
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from helpers import (
    transport_params,
    SYSTEM_MESSAGE,
    tools_list,
    tools_schema,
    create_stt_service,
    create_tts_service,
    create_llm_service,
    STTLogger,
    TimingProcessor,
    TimingStats
)


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    """Configura y ejecuta el bot de voz"""
    print("Starting bot")

    async with aiohttp.ClientSession() as session:
        # Crear servicios
        stt = create_stt_service()
        tts = create_tts_service(session)
        llm = create_llm_service()
        
        # Crear sistema de timing
        timing_stats = TimingStats()

        # Configurar mensajes y contexto (system prompt y tools)
        for tool in tools_list:
            llm.register_direct_function(handler=tool, cancel_on_interruption=True)
        messages = [{"role": "system", "content": SYSTEM_MESSAGE}]
        context = LLMContext(
            messages,
            tools=tools_schema
        )

        # Configurar agregadores con estrategias de turn
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

        # Construir pipeline con procesadores de timing
        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                TimingProcessor("stt", timing_stats),
                # STTLogger(),
                user_aggregator,
                llm,
                TimingProcessor("llm", timing_stats),
                tts,
                TimingProcessor("tts", timing_stats),
                transport.output(),
                assistant_aggregator
            ]
        )

        # Crear task con métricas y tracing habilitados
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            enable_tracing=True,
            enable_turn_tracking=True,
            idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        )

        # Event handlers
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
            timing_stats.print_stats()
            await task.cancel()

        # Ejecutar pipeline
        runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
        await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Punto de entrada del bot"""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
