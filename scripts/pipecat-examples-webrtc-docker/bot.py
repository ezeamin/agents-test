#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import os

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
# from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.services.aws.stt import AWSTranscribeSTTService
from pipecat.services.aws.llm import AWSBedrockLLMService
from pipecat.services.aws.tts import PollyTTSService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

load_dotenv(override=True)

SYSTEM_INSTRUCTION = f"""
"You are Gemini Chatbot, a friendly, helpful robot.

Your goal is to demonstrate your capabilities in a succinct way.

Your output will be converted to audio so don't include special characters in your answers.

Respond to what the user said in a creative and helpful way. Keep your responses brief. One or two sentences at most.
"""


async def run_bot(webrtc_connection):
    pipecat_transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_10ms_chunks=2,
        ),
    )

    # llm = GeminiLiveLLMService(
    #     api_key=os.getenv("GOOGLE_API_KEY"),
    #     voice_id="Puck",  # Aoede, Charon, Fenrir, Kore, Puck
    #     system_instruction=SYSTEM_INSTRUCTION,
    # )

    stt = AWSTranscribeSTTService(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id")),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key")),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token")),
        region=os.getenv("AWS_DEFAULT_REGION", os.getenv("aws_default_region", "us-east-1")),
    )

    llm = AWSBedrockLLMService(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id")),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key")),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token")),
        region=os.getenv("AWS_DEFAULT_REGION", os.getenv("aws_default_region", "us-east-1")),
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    
    tts = PollyTTSService(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", os.getenv("aws_access_key_id")),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("aws_secret_access_key")),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", os.getenv("aws_session_token")),
        region=os.getenv("AWS_DEFAULT_REGION", os.getenv("aws_default_region", "us-east-1")),
    )

    context = LLMContext(
        [
            {
                "role": "user",
                "content": "Start by greeting the user warmly and introducing yourself.",
            }
        ],
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    pipeline = Pipeline(
        [
            pipecat_transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            pipecat_transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @pipecat_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Pipecat Client connected")
        # Kick off the conversation.
        await task.queue_frames([LLMRunFrame()])

    @pipecat_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Pipecat Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)