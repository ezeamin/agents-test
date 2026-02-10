from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.whisper.stt import WhisperSTTService, Model
from pipecat.services.aws.llm import AWSBedrockLLMService
from pipecat.services.piper.tts import PiperTTSService
from pipecat.frames.frames import Frame, MetricsFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.metrics.metrics import TTFBMetricsData, ProcessingMetricsData, LLMUsageMetricsData

# Custom metrics logger
class MetricsLogger(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, MetricsFrame):
            for d in frame.data:
                if isinstance(d, TTFBMetricsData):
                    print(f"TTFB: {d.value}s")
                elif isinstance(d, ProcessingMetricsData):
                    print(f"Processing: {d.value}s")
                elif isinstance(d, LLMUsageMetricsData):
                    print(f"Tokens - prompt: {d.value.prompt_tokens}, completion: {d.value.completion_tokens}")
        await self.push_frame(frame, direction)

# Services
stt = WhisperSTTService(model=Model.DISTIL_MEDIUM_EN, device="auto")
llm = AWSBedrockLLMService(model="anthropic.claude-3-sonnet")  # Bedrock streams by default
tts = PiperTTSService(base_url="http://localhost:5000", aiohttp_session=session)

# Pipeline with metrics
pipeline = Pipeline([
    transport.input(),
    stt,
    context_aggregator.user(),
    llm,
    tts,
    transport.output(),
    context_aggregator.assistant(),
    MetricsLogger(),
])

task = PipelineTask(
    pipeline,
    params=PipelineParams(
        enable_metrics=True,
        enable_usage_metrics=True,  # For token counts
    ),
)