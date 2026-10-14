import logging
import math
import uuid
import tempfile
import os
import hashlib
from typing import Optional, List, Dict, Any
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from app.core.config import settings
from app.models.source_version import SourceVersion, ProcessingStatus, SourceType
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.services.pdf_ingestion import ProcessingResult, AlreadyProcessedError, _count_existing_evidence
from app.services.media_tools import MediaTools, MediaProbeError
from app.services.derived_storage import derived_dir_for, safe_derived_filename
from app.services.transcription import TranscriptionProvider, MLXWhisperProvider

logger = logging.getLogger(__name__)

class VideoProcessingError(Exception):
    pass

class NotAVideoError(Exception):
    pass

class VideoDependencyError(Exception):
    pass

def _hash_file(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def _select_representative_frames(
    frames: list[dict],
    duration: float,
    min_gap: float,
    max_frames: int,
) -> list[dict]:
    """
    Select representative frames only from real ffprobe-decoded frames.

    Mathematical target positions may guide selection, but every returned
    timestamp is copied from an actual decoded frame.
    """
    if max_frames <= 0:
        return []

    usable: list[dict] = []

    for frame in frames:
        try:
            timestamp = float(frame["timestamp_seconds"])
            frame_index = int(frame["frame_index"])
        except (KeyError, TypeError, ValueError):
            continue

        if not math.isfinite(timestamp) or timestamp < 0:
            continue

        # Do not expose a citation beyond the known source duration.
        if duration > 0 and timestamp > duration:
            continue

        candidate = dict(frame)
        candidate["timestamp_seconds"] = timestamp
        candidate["frame_index"] = frame_index
        usable.append(candidate)

    if not usable:
        return []

    usable.sort(
        key=lambda frame: (
            frame["timestamp_seconds"],
            frame["frame_index"],
        )
    )

    min_gap = max(0.0, float(min_gap))
    selected: list[dict] = []
    selected_indexes: set[int] = set()

    def far_enough(candidate: dict) -> bool:
        timestamp = candidate["timestamp_seconds"]
        return all(
            abs(timestamp - existing["timestamp_seconds"]) >= min_gap
            for existing in selected
        )

    def add(candidate: dict, method: str) -> bool:
        if len(selected) >= max_frames:
            return False

        frame_index = candidate["frame_index"]

        if frame_index in selected_indexes:
            return False

        if selected and not far_enough(candidate):
            return False

        chosen = dict(candidate)
        chosen["selection_method"] = method

        selected.append(chosen)
        selected_indexes.add(frame_index)
        return True

    # The first actual decoded frame is always useful provenance.
    first = dict(usable[0])
    first["selection_method"] = "first_decoded_frame"
    selected.append(first)
    selected_indexes.add(first["frame_index"])

    if len(selected) >= max_frames:
        return selected

    span = duration if duration > 0 else usable[-1]["timestamp_seconds"]

    if max_frames > 1 and span > 0:
        targets = [
            span * position / max_frames
            for position in range(1, max_frames)
        ]
    else:
        targets = []

    # Prefer real keyframes distributed across the source.
    keyframes = [
        frame
        for frame in usable
        if frame.get("key_frame")
        and frame["frame_index"] not in selected_indexes
    ]

    for target in targets:
        if len(selected) >= max_frames:
            break

        candidates = [
            frame
            for frame in keyframes
            if frame["frame_index"] not in selected_indexes
            and far_enough(frame)
        ]

        if not candidates:
            continue

        candidate = min(
            candidates,
            key=lambda frame: abs(frame["timestamp_seconds"] - target),
        )
        add(candidate, "keyframe")

    # If keyframes are sparse, fill remaining slots using nearest actual
    # decoded frames. Targets guide selection only; stored timestamps remain
    # the real ffprobe timestamps.
    for target in targets:
        if len(selected) >= max_frames:
            break

        candidates = [
            frame
            for frame in usable
            if frame["frame_index"] not in selected_indexes
            and far_enough(frame)
        ]

        if not candidates:
            continue

        candidate = min(
            candidates,
            key=lambda frame: abs(frame["timestamp_seconds"] - target),
        )
        add(candidate, "decoded_frame_fallback")

    selected.sort(
        key=lambda frame: (
            frame["timestamp_seconds"],
            frame["frame_index"],
        )
    )

    return selected


async def process_video(
    db: AsyncSession,
    *,
    source_version: SourceVersion,
    transcription_provider: Optional[TranscriptionProvider] = None
) -> ProcessingResult:
    sv_id = source_version.id

    if source_version.source_type != SourceType.video:
        raise NotAVideoError(f"SourceVersion {sv_id} is {source_version.source_type.value}, not video")

    if source_version.processing_status == ProcessingStatus.ready:
        existing_count = await _count_existing_evidence(db, sv_id)

        # Read duration from metadata
        stmt = select(EvidenceUnit.location_metadata).where(
            EvidenceUnit.source_version_id == sv_id,
            EvidenceUnit.location_metadata.op("->>")("source_duration_seconds").is_not(None)
        ).limit(1)
        duration_res = await db.execute(stmt)
        duration_meta = duration_res.scalar_one_or_none()
        parsed_duration = None
        if duration_meta is not None:
             parsed_duration = float(duration_meta.get("source_duration_seconds", 0.0))

        result = ProcessingResult(
            source_version_id=sv_id,
            processing_status="ready",
            already_processed=True,
            duration_seconds=parsed_duration,
            page_count=None,
            slide_count=None,
            **existing_count,
        )
        raise AlreadyProcessedError(result)

    source_version.processing_status = ProcessingStatus.processing
    await db.commit()
    await db.refresh(source_version)

    video_path = source_version.storage_path
    if not os.path.exists(video_path):
        source_version.processing_status = ProcessingStatus.failed
        await db.commit()
        raise VideoProcessingError(f"Video file not found: {video_path}")

    # Verify initial hash
    initial_hash = _hash_file(video_path)

    media_tools = MediaTools(timeout_seconds=settings.video_subprocess_timeout_seconds)
    if transcription_provider is None:
        transcription_provider = MLXWhisperProvider(model_name=settings.video_transcription_model)

    result = ProcessingResult(
        source_version_id=sv_id,
        processing_status="processing",
        page_count=None,
        slide_count=None,
    )
    result.text_evidence_count = 0
    result.table_evidence_count = 0
    result.image_evidence_count = 0
    result.video_evidence_count = 0

    evidence_units: List[EvidenceUnit] = []
    derived_dir = derived_dir_for(sv_id)
    derived_dir.mkdir(parents=True, exist_ok=True)
    video_derived_dir = derived_dir / "video"
    video_derived_dir.mkdir(exist_ok=True)

    created_files = []

    try:
        # Probe media
        probe = media_tools.probe_media(video_path)
        format_info = probe.get("format", {})
        streams = probe.get("streams", [])

        duration = float(format_info.get("duration", 0.0))
        result.duration_seconds = duration

        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        has_video = any(s.get("codec_type") == "video" for s in streams)

        if not has_audio and not has_video:
            raise VideoProcessingError("No usable video or audio streams found")

        if not has_audio:
            result.warnings.append("no_audio_stream")
        if not has_video:
            result.warnings.append("no_video_stream")

        if has_audio:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_audio = os.path.join(temp_dir, "audio.wav")
                media_tools.extract_audio(video_path, temp_audio)

                transcription_result = await transcription_provider.transcribe(temp_audio)

                for idx, segment in enumerate(transcription_result.segments):
                    text = segment.text.strip()
                    if not text:
                        continue

                    start_seconds = float(segment.start_seconds)
                    provider_end_seconds = float(segment.end_seconds)

                    if not math.isfinite(start_seconds) or not math.isfinite(provider_end_seconds):
                        raise VideoProcessingError(
                            f"Non-finite timestamp in segment: "
                            f"start={segment.start_seconds}, end={segment.end_seconds}"
                        )

                    if start_seconds < 0 or provider_end_seconds < start_seconds:
                        raise VideoProcessingError(
                            f"Invalid timestamp in segment: "
                            f"start={start_seconds}, end={provider_end_seconds}"
                        )

                    citation_end_seconds = provider_end_seconds
                    timestamp_adjusted = False

                    if duration > 0:
                        if start_seconds > duration:
                            raise VideoProcessingError(
                                f"Impossible timestamp beyond media duration: "
                                f"start={start_seconds}, duration={duration}"
                            )

                        overshoot = provider_end_seconds - duration

                        if overshoot > 1.0:
                            raise VideoProcessingError(
                                f"Impossible end timestamp beyond media duration: "
                                f"end={provider_end_seconds}, duration={duration}"
                            )

                        if overshoot > 0:
                            citation_end_seconds = duration
                            timestamp_adjusted = True

                    loc_meta = {
                        "element_type": "transcript_segment",
                        "segment_index": idx,
                        "start_seconds": start_seconds,
                        "end_seconds": citation_end_seconds,
                        "start_ms": int(start_seconds * 1000),
                        "end_ms": int(citation_end_seconds * 1000),
                        "source_duration_seconds": duration if duration > 0 else None,
                    }

                    if timestamp_adjusted:
                        loc_meta["provider_end_seconds"] = provider_end_seconds
                        loc_meta["provider_end_ms"] = int(provider_end_seconds * 1000)
                        loc_meta["timestamp_adjustment"] = "bounded_to_source_duration"
                    if segment.language:
                        loc_meta["language"] = segment.language
                    if segment.timestamp_source:
                        loc_meta["timestamp_source"] = segment.timestamp_source

                    eu = EvidenceUnit(
                        course_id=source_version.course_id,
                        source_version_id=sv_id,
                        modality=Modality.video,
                        original_text=segment.text,
                        extracted_description=None,
                        topic=None,
                        subtopic=None,
                        extraction_status=ExtractionStatus.extracted,
                        location_metadata=loc_meta
                    )
                    evidence_units.append(eu)
                    result.video_evidence_count += 1

        if has_video:
            decoded_frames = media_tools.probe_video_frames(video_path)

            selected_frames = _select_representative_frames(
                frames=decoded_frames,
                duration=duration,
                min_gap=settings.video_min_frame_gap_seconds,
                max_frames=settings.video_max_frames,
            )

            if not selected_frames:
                result.warnings.append("no_decodable_video_frames")

                if not has_audio:
                    raise VideoProcessingError(
                        "Video stream contained no decodable frames"
                    )

            for idx, frame in enumerate(selected_frames):
                timestamp = float(frame["timestamp_seconds"])
                source_frame_index = int(frame["frame_index"])

                filename = (
                    f"frame_{idx:03d}_src_{source_frame_index}_"
                    f"{int(timestamp * 1000)}.jpg"
                )
                output_path = video_derived_dir / filename

                # Register the path before extraction so even a partially
                # written FFmpeg output is removed on failure.
                created_files.append(str(output_path))

                media_tools.extract_frame_by_index(
                    video_path,
                    source_frame_index,
                    str(output_path),
                )

                loc_meta = {
                    "element_type": "video_frame",
                    "frame_index": idx,
                    "source_frame_index": source_frame_index,
                    "timestamp_seconds": timestamp,
                    "timestamp_ms": int(timestamp * 1000),
                    "timestamp_source": frame.get(
                        "timestamp_source",
                        "ffprobe_decoded_frame",
                    ),
                    "derived_path": str(output_path),
                    "image_width": frame.get("width"),
                    "image_height": frame.get("height"),
                    "key_frame": bool(frame.get("key_frame", False)),
                    "selection_method": frame["selection_method"],
                    "source_duration_seconds": (
                        duration if duration > 0 else None
                    ),
                }

                eu = EvidenceUnit(
                    course_id=source_version.course_id,
                    source_version_id=sv_id,
                    modality=Modality.image,
                    original_text=None,
                    extraction_status=ExtractionStatus.extracted,
                    location_metadata=loc_meta,
                )
                evidence_units.append(eu)
                result.image_evidence_count += 1

        # Check immutability
        final_hash = _hash_file(video_path)
        if initial_hash != final_hash:
            raise VideoProcessingError("Source file was modified during processing")

        if evidence_units:
            db.add_all(evidence_units)
            await db.flush()

        source_version.processing_status = ProcessingStatus.ready
        result.processing_status = "ready"
        await db.commit()

    except Exception as exc:
        await db.rollback()
        # Clean up files created
        for fpath in created_files:
            try:
                os.remove(fpath)
            except OSError:
                pass

        logger.error("Video processing failed: source_version_id=%s, error=%s", sv_id, exc)
        source_version.processing_status = ProcessingStatus.failed
        await db.commit()
        if isinstance(exc, (VideoProcessingError, MediaProbeError)):
            raise VideoProcessingError(str(exc)) from exc
        raise VideoProcessingError(str(exc)) from exc

    return result
