import os
import uuid
import tempfile
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.source_version import SourceVersion, SourceType, ProcessingStatus
from app.models.evidence_unit import EvidenceUnit, Modality, ExtractionStatus
from app.services.video_ingestion import (
    process_video,
    VideoProcessingError,
    NotAVideoError,
)
from tests.fake_transcription import FakeTranscriptionProvider
from sqlalchemy import select

class FakeMediaTools:
    def __init__(self, has_video=True, has_audio=True):
        self.has_video = has_video
        self.has_audio = has_audio

    def probe_media(self, file_path):
        import json
        streams = []
        if self.has_video:
            streams.append({"codec_type": "video"})
        if self.has_audio:
            streams.append({"codec_type": "audio"})
        return {
            "format": {"duration": "10.0"},
            "streams": streams
        }

    def extract_audio(self, video_path, output_path):
        with open(output_path, "w") as f:
            f.write("fake audio")

    def probe_video_frames(self, file_path):
        if not self.has_video:
            return []

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
                "frame_index": 51,
                "timestamp_seconds": 2.04,
                "timestamp_source": "ffprobe_best_effort_timestamp_time",
                "key_frame": False,
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
                "frame_index": 153,
                "timestamp_seconds": 6.12,
                "timestamp_source": "ffprobe_best_effort_timestamp_time",
                "key_frame": False,
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
            {
                "frame_index": 249,
                "timestamp_seconds": 9.96,
                "timestamp_source": "ffprobe_best_effort_timestamp_time",
                "key_frame": False,
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

@pytest.fixture
def fake_media_tools(monkeypatch):
    def patch_media_tools(*args, **kwargs):
        from app.services.video_ingestion import MediaTools
        return FakeMediaTools()
    monkeypatch.setattr("app.services.video_ingestion.MediaTools", patch_media_tools)
    import app.services.source_processing
    monkeypatch.setattr("app.services.source_processing.get_default_transcription_provider", lambda: FakeTranscriptionProvider(), raising=False)

@pytest_asyncio.fixture
async def sample_video_source(db_session: AsyncSession):
    course_id = uuid.uuid4()
    sv = SourceVersion(
        course_id=course_id,
        original_filename="test.mp4",
        file_hash="dummyhash",
        mime_type="video/mp4",
        source_type=SourceType.video,
        storage_path="",
        processing_status=ProcessingStatus.uploaded,
    )
    db_session.add(sv)
    await db_session.commit()
    await db_session.refresh(sv)

    # Create fake file
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.write(fd, b"fake video content")
    os.close(fd)

    sv.storage_path = path
    db_session.add(sv)
    await db_session.commit()

    yield sv

    try:
        os.remove(path)
    except:
        pass

@pytest.mark.asyncio
async def test_process_video_success(db_session: AsyncSession, sample_video_source: SourceVersion, fake_media_tools):
    transcription_provider = FakeTranscriptionProvider()

    result = await process_video(
        db_session,
        source_version=sample_video_source,
        transcription_provider=transcription_provider
    )

    assert result.processing_status == "ready"
    assert result.duration_seconds == 10.0
    assert result.video_evidence_count == 1
    assert result.image_evidence_count > 0

    # Check DB Evidence
    stmt = select(EvidenceUnit).where(EvidenceUnit.source_version_id == sample_video_source.id)
    db_result = await db_session.execute(stmt)
    units = list(db_result.scalars().all())

    video_units = [u for u in units if u.modality == Modality.video]
    assert len(video_units) == 1

    v_eu = video_units[0]
    assert v_eu.original_text == "This is a test transcript."
    loc = v_eu.location_metadata
    assert loc["element_type"] == "transcript_segment"
    assert loc["start_seconds"] == 1.0
    assert loc["end_seconds"] == 5.0
    assert loc["start_ms"] == 1000
    assert loc["end_ms"] == 5000
    assert loc["timestamp_source"] == "fake_segment"

    image_units = [u for u in units if u.modality == Modality.image]
    assert len(image_units) == result.image_evidence_count

    actual_decoded_timestamps = {
        0.0,
        2.04,
        4.08,
        6.12,
        8.16,
        9.96,
    }

    for image_unit in image_units:
        frame_loc = image_unit.location_metadata

        # Citation timestamps must come from actual decoded frames,
        # never from mathematically generated sampling positions.
        assert frame_loc["timestamp_seconds"] in actual_decoded_timestamps
        assert (
            frame_loc["timestamp_source"]
            == "ffprobe_best_effort_timestamp_time"
        )
        assert frame_loc["image_width"] == 320
        assert frame_loc["image_height"] == 240
        assert frame_loc["source_duration_seconds"] == 10.0
        assert isinstance(frame_loc["source_frame_index"], int)
        assert frame_loc["selection_method"] in {
            "first_decoded_frame",
            "keyframe",
            "decoded_frame_fallback",
        }
        assert frame_loc["selection_method"] != "uniform_fallback"

@pytest.mark.asyncio
async def test_process_video_not_a_video(db_session: AsyncSession):
    sv = SourceVersion(
        id=uuid.uuid4(),
        course_id=uuid.uuid4(),
        original_filename="test.pdf",
        file_hash="dummy",
        mime_type="application/pdf",
        source_type=SourceType.pdf,
        storage_path="doesn_matter",
        processing_status=ProcessingStatus.uploaded,
    )
    with pytest.raises(NotAVideoError):
        await process_video(db_session, source_version=sv, transcription_provider=FakeTranscriptionProvider())

@pytest.mark.asyncio
async def test_process_video_duplicate_idempotency(db_session: AsyncSession, sample_video_source: SourceVersion, fake_media_tools):
    transcription_provider = FakeTranscriptionProvider()

    res1 = await process_video(
        db_session,
        source_version=sample_video_source,
        transcription_provider=transcription_provider
    )

    # Refresh sv
    await db_session.refresh(sample_video_source)

    # Process again
    from app.services.pdf_ingestion import AlreadyProcessedError

    with pytest.raises(AlreadyProcessedError) as exc:
         await process_video(db_session, source_version=sample_video_source, transcription_provider=transcription_provider)

    res2 = exc.value.result
    assert res2.already_processed is True
    assert res2.video_evidence_count == res1.video_evidence_count
    assert res2.image_evidence_count == res1.image_evidence_count

@pytest.mark.asyncio
async def test_process_video_invalid_timestamp_rejected(db_session: AsyncSession, sample_video_source: SourceVersion, monkeypatch, fake_media_tools):
    transcription_provider = FakeTranscriptionProvider()
    transcription_provider.segments[0].start_seconds = -1.0 # Invalid negative timestamp

    with pytest.raises(VideoProcessingError) as exc:
        await process_video(
            db_session,
            source_version=sample_video_source,
            transcription_provider=transcription_provider
        )
    assert "Invalid timestamp" in str(exc.value)

@pytest.mark.asyncio
async def test_process_video_beyond_duration_timestamp_rejected(db_session: AsyncSession, sample_video_source: SourceVersion, fake_media_tools):
    transcription_provider = FakeTranscriptionProvider()
    transcription_provider.segments[0].start_seconds = 20.0 # Beyond duration 10.0

    with pytest.raises(VideoProcessingError) as exc:
        await process_video(
            db_session,
            source_version=sample_video_source,
            transcription_provider=transcription_provider
        )
    assert "Invalid timestamp" in str(exc.value)

    # Must wait for refresh before checking status
    await db_session.refresh(sample_video_source)
    assert sample_video_source.processing_status == ProcessingStatus.failed

@pytest.mark.asyncio
async def test_process_video_no_audio(db_session: AsyncSession, sample_video_source: SourceVersion, monkeypatch):
    class NoAudioTools(FakeMediaTools):
         def __init__(self):
             super().__init__(has_video=True, has_audio=False)

    monkeypatch.setattr("app.services.video_ingestion.MediaTools", lambda **k: NoAudioTools())

    transcription_provider = FakeTranscriptionProvider()

    res = await process_video(
        db_session,
        source_version=sample_video_source,
        transcription_provider=transcription_provider
    )
    assert res.processing_status == "ready"
    assert "no_audio_stream" in res.warnings
    assert res.video_evidence_count == 0
    assert res.image_evidence_count > 0

@pytest.mark.asyncio
async def test_process_video_no_video(db_session: AsyncSession, sample_video_source: SourceVersion, monkeypatch):
    class NoVideoTools(FakeMediaTools):
         def __init__(self):
             super().__init__(has_video=False, has_audio=True)

    monkeypatch.setattr("app.services.video_ingestion.MediaTools", lambda **k: NoVideoTools())

    transcription_provider = FakeTranscriptionProvider()

    res = await process_video(
        db_session,
        source_version=sample_video_source,
        transcription_provider=transcription_provider
    )
    assert res.processing_status == "ready"
    assert "no_video_stream" in res.warnings
    assert res.video_evidence_count == 1
    assert res.image_evidence_count == 0

@pytest.mark.asyncio
async def test_process_video_no_usable_stream(db_session: AsyncSession, sample_video_source: SourceVersion, monkeypatch):
    class NoStreamsTools(FakeMediaTools):
         def __init__(self):
             super().__init__(has_video=False, has_audio=False)

    monkeypatch.setattr("app.services.video_ingestion.MediaTools", lambda **k: NoStreamsTools())

    transcription_provider = FakeTranscriptionProvider()

    with pytest.raises(VideoProcessingError) as exc:
        await process_video(
            db_session,
            source_version=sample_video_source,
            transcription_provider=transcription_provider
        )

    assert "No usable video or audio streams found" in str(exc.value)




@pytest.mark.asyncio
async def test_process_video_small_terminal_timestamp_overshoot_is_bounded(
    db_session: AsyncSession,
    sample_video_source: SourceVersion,
    fake_media_tools,
):
    transcription_provider = FakeTranscriptionProvider()
    transcription_provider.segments[0].start_seconds = 0.0
    transcription_provider.segments[0].end_seconds = 10.2

    result = await process_video(
        db_session,
        source_version=sample_video_source,
        transcription_provider=transcription_provider,
    )

    assert result.processing_status == "ready"

    stmt = select(EvidenceUnit).where(
        EvidenceUnit.source_version_id == sample_video_source.id,
        EvidenceUnit.modality == Modality.video,
    )
    db_result = await db_session.execute(stmt)
    unit = db_result.scalars().one()

    loc = unit.location_metadata

    assert loc["start_seconds"] == 0.0
    assert loc["end_seconds"] == 10.0
    assert loc["provider_end_seconds"] == 10.2
    assert loc["provider_end_ms"] == 10200
    assert loc["end_ms"] == 10000
    assert loc["timestamp_adjustment"] == "bounded_to_source_duration"
    assert loc["source_duration_seconds"] == 10.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overshoot, accepted",
    [(0.541, True), (1.1, False)],
)
async def test_terminal_timestamp_overshoot_boundary(
    db_session,
    sample_video_source,
    fake_media_tools,
    overshoot,
    accepted,
):
    provider = FakeTranscriptionProvider()
    provider.segments[0].start_seconds = 9.0
    provider.segments[0].end_seconds = 10.0 + overshoot

    if not accepted:
        with pytest.raises(VideoProcessingError, match="Impossible end timestamp"):
            await process_video(
                db_session,
                source_version=sample_video_source,
                transcription_provider=provider,
            )
        await db_session.refresh(sample_video_source)
        assert sample_video_source.processing_status == ProcessingStatus.failed
        return

    result = await process_video(
        db_session,
        source_version=sample_video_source,
        transcription_provider=provider,
    )
    assert result.processing_status == "ready"

    units = (
        await db_session.scalars(
            select(EvidenceUnit).where(
                EvidenceUnit.source_version_id == sample_video_source.id,
                EvidenceUnit.modality == Modality.video,
            )
        )
    ).all()

    assert len(units) == 1
    metadata = units[0].location_metadata
    assert metadata["end_seconds"] == 10.0
    assert metadata["provider_end_seconds"] == pytest.approx(10.0 + overshoot)
    assert metadata["timestamp_adjustment"] == "bounded_to_source_duration"
