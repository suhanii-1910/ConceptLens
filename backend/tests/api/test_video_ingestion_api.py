import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import Optional
from app.models.evidence_unit import EvidenceUnit
from sqlalchemy import select

class FakeMediaTools:
    def probe_media(self, file_path):
        return {
            "format": {"duration": "10.0"},
            "streams": [{"codec_type": "video"}, {"codec_type": "audio"}]
        }

    def extract_audio(self, video_path, output_path):
        with open(output_path, "w") as f:
            f.write("fake audio")

    def probe_video_frames(self, file_path):
        return [
            {
                "frame_index": 0,
                "timestamp_seconds": 0.0,
                "timestamp_source": "ffprobe_best_effort_timestamp_time",
                "key_frame": True,
                "width": 320,
                "height": 240,
            },
            {
                "frame_index": 102,
                "timestamp_seconds": 4.08,
                "timestamp_source": "ffprobe_best_effort_timestamp_time",
                "key_frame": True,
                "width": 320,
                "height": 240,
            },
            {
                "frame_index": 204,
                "timestamp_seconds": 8.16,
                "timestamp_source": "ffprobe_best_effort_timestamp_time",
                "key_frame": True,
                "width": 320,
                "height": 240,
            },
        ]

    def extract_frame_by_index(
        self,
        video_path,
        frame_index,
        output_path,
    ):
        with open(output_path, "wb") as f:
            f.write(b"fake image data")

class FakeTranscriptionProvider:
    def __init__(self):
        from app.services.transcription import TranscriptionSegment
        self.segments = [
            TranscriptionSegment(
                start_seconds=1.0,
                end_seconds=5.0,
                text="This is a test transcript."
            )
        ]

    async def transcribe(self, audio_path: str):
        from app.services.transcription import TranscriptionResult
        return TranscriptionResult(segments=self.segments)


@pytest.fixture
def mock_video_tools(monkeypatch):
    import app.services.video_ingestion
    monkeypatch.setattr("app.services.video_ingestion.MediaTools", lambda **kwargs: FakeMediaTools())
    # The default transcription provider in video_ingestion is MLXWhisperProvider(model_name=settings.video_transcription_model)
    # the instantiation happens within process_video:
    # if transcription_provider is None:
    #     transcription_provider = MLXWhisperProvider(model_name=settings.video_transcription_model)
    monkeypatch.setattr("app.services.video_ingestion.MLXWhisperProvider", lambda **kwargs: FakeTranscriptionProvider())

@pytest.mark.asyncio
async def test_process_video_api(client: AsyncClient, db_session: AsyncSession, mock_video_tools):
    resp = await client.post("/courses", json={"name": "Video Processing API"})
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    mp4_bytes = b"\x00\x00\x00\x18ftypmp42fakevideodata"
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files={"file": ("test.mp4", mp4_bytes, "video/mp4")},
    )
    assert resp.status_code == 201
    source_version_id = resp.json()["id"]

    # Trigger processing
    resp = await client.post(f"/courses/{course_id}/sources/{source_version_id}/process")
    assert resp.status_code == 201
    data = resp.json()
    assert data["processing_status"] == "ready"
    assert data["duration_seconds"] == 10.0
    assert data["video_evidence_count"] == 1
    assert data["image_evidence_count"] > 0

    # Verify in DB
    result = await db_session.execute(
        select(EvidenceUnit).where(EvidenceUnit.source_version_id == uuid.UUID(source_version_id))
    )
    units = result.scalars().all()
    assert len(units) > 1
