"""Procesadores customizados del pipeline"""
from pipecat.frames.frames import TextFrame
from pipecat.processors.frame_processor import FrameProcessor


class STTLogger(FrameProcessor):
    """Logger que guarda las transcripciones de STT en un archivo"""
    
    def __init__(self, filename="logs/stt_log.txt"):
        super().__init__()
        self.filename = filename

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame):
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(frame.text + "\n")
