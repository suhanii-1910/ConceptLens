from app.services.transcription import TranscriptionProvider, TranscriptionResult, TranscriptionSegment

class FakeTranscriptionProvider:
    """Deterministic fake provider for automated tests."""
    def __init__(self):
        self.fail_on_next = False
        self.segments = [
            TranscriptionSegment(
                text="This is a test transcript.",
                start_seconds=1.0,
                end_seconds=5.0,
                timestamp_source="fake_segment"
            )
        ]

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        if self.fail_on_next:
            self.fail_on_next = False
            raise RuntimeError("Fake transcription failure")
        return TranscriptionResult(segments=self.segments)

def get_fake_transcription_provider() -> TranscriptionProvider:
    return FakeTranscriptionProvider()
