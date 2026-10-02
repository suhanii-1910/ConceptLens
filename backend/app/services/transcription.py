import logging
from typing import Protocol, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TranscriptionSegment:
    text: str
    start_seconds: float
    end_seconds: float
    language: Optional[str] = None
    confidence: Optional[float] = None
    timestamp_source: Optional[str] = None

@dataclass
class TranscriptionResult:
    segments: List[TranscriptionSegment]

class TranscriptionProvider(Protocol):
    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        ...

class MLXWhisperProvider:
    def __init__(self, model_name: str):
        self.model_name = model_name

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        try:
            import mlx_whisper
        except ImportError:
            raise RuntimeError(
                "mlx-whisper not installed. Ensure you're in an appropriate environment."
            )

        logger.info(f"Transcribing audio {audio_path} using {self.model_name}")
        import asyncio
        loop = asyncio.get_running_loop()

        def _run_transcribe():
            return mlx_whisper.transcribe(audio_path, path_or_hf_repo=self.model_name)

        result_dict = await loop.run_in_executor(None, _run_transcribe)

        segments = []
        for seg in result_dict.get("segments", []):
            segments.append(TranscriptionSegment(
                text=seg.get("text", ""),
                start_seconds=seg.get("start", 0.0),
                end_seconds=seg.get("end", 0.0),
                language=result_dict.get("language"),
                confidence=None,
                timestamp_source="mlx_whisper_segment"
            ))

        return TranscriptionResult(segments=segments)

def get_default_transcription_provider() -> TranscriptionProvider:
    from app.core.config import settings
    return MLXWhisperProvider(model_name=settings.video_transcription_model)
