from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from faster_whisper import WhisperModel

from app.jobs import augment_manifest, human_duration, read_manifest, save_manifest


@dataclass(frozen=True)
class TranscriptionProfile:
    model_name: str
    beam_size: int
    best_of: int
    vad_filter: bool
    compute_type: str = "int8"
    device: str = "cpu"


PROFILE_MAP: dict[str, TranscriptionProfile] = {
    "fast": TranscriptionProfile(
        model_name="small",
        beam_size=1,
        best_of=1,
        vad_filter=True,
    ),
    "balanced": TranscriptionProfile(
        model_name="medium",
        beam_size=3,
        best_of=3,
        vad_filter=True,
    ),
    "best": TranscriptionProfile(
        model_name="large-v3",
        beam_size=5,
        best_of=5,
        vad_filter=True,
    ),
}


def get_profile(profile_name: str) -> TranscriptionProfile:
    try:
        return PROFILE_MAP[profile_name]
    except KeyError as exc:
        known = ", ".join(sorted(PROFILE_MAP))
        raise ValueError(f"Unknown profile '{profile_name}'. Expected one of: {known}") from exc


def create_model(profile_name: str) -> WhisperModel:
    profile = get_profile(profile_name)
    return WhisperModel(
        profile.model_name,
        device=profile.device,
        compute_type=profile.compute_type,
    )


def transcript_output_paths(media_path: Path) -> dict[str, Path]:
    stem = media_path.with_suffix("")
    return {
        "txt": Path(f"{stem}.transcript.txt"),
        "srt": Path(f"{stem}.transcript.srt"),
        "json": Path(f"{stem}.transcript.json"),
    }


def format_srt_timestamp(seconds: float) -> str:
    total_milliseconds = round(seconds * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def build_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        text = segment["text"].strip()
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(segment['start'])} --> {format_srt_timestamp(segment['end'])}",
                    text,
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def transcribe_media(
    media_path: str | Path,
    profile_name: str = "balanced",
    *,
    model: WhisperModel | None = None,
) -> dict[str, Any]:
    source = Path(media_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Media file does not exist: {source}")
    if not source.is_file():
        raise ValueError(f"Media path is not a file: {source}")

    profile = get_profile(profile_name)
    outputs = transcript_output_paths(source)
    active_model = model or create_model(profile_name)

    started = perf_counter()
    segments_iter, info = active_model.transcribe(
        str(source),
        beam_size=profile.beam_size,
        best_of=profile.best_of,
        vad_filter=profile.vad_filter,
        condition_on_previous_text=True,
        multilingual=True,
        task="transcribe",
    )

    segments: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for segment in segments_iter:
        segment_payload = {
            "id": segment.id,
            "seek": segment.seek,
            "start": float(segment.start),
            "end": float(segment.end),
            "text": segment.text.strip(),
            "avg_logprob": float(segment.avg_logprob),
            "compression_ratio": float(segment.compression_ratio),
            "no_speech_prob": float(segment.no_speech_prob),
        }
        segments.append(segment_payload)
        text_parts.append(segment_payload["text"])

    transcript_text = "\n".join(part for part in text_parts if part).strip() + "\n"
    srt_text = build_srt(segments)
    elapsed_seconds = perf_counter() - started

    payload = {
        "source_path": str(source),
        "profile": profile_name,
        "model_name": profile.model_name,
        "language": info.language,
        "language_probability": float(info.language_probability),
        "duration": float(info.duration),
        "duration_after_vad": float(info.duration_after_vad),
        "elapsed_seconds": elapsed_seconds,
        "elapsed_human": human_duration(elapsed_seconds),
        "transcript_txt": str(outputs["txt"]),
        "transcript_srt": str(outputs["srt"]),
        "transcript_json": str(outputs["json"]),
        "segments": segments,
    }

    ensure_parent(outputs["txt"])
    outputs["txt"].write_text(transcript_text, encoding="utf-8")
    outputs["srt"].write_text(srt_text, encoding="utf-8")
    outputs["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return payload


def transcribe_file(media_path: str | Path, profile_name: str = "balanced") -> dict[str, Any]:
    model = create_model(profile_name)
    return transcribe_media(media_path, profile_name=profile_name, model=model)


def run_job_manifest(manifest_path: str | Path, stop_event: Any | None = None) -> dict[str, Any]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = read_manifest(manifest_file)
    profile = manifest["profile"]
    model = create_model(profile)
    results: list[dict[str, Any]] = []

    manifest["status"] = "running"
    manifest["started_at"] = manifest.get("started_at") or datetime.now(UTC).isoformat()
    save_manifest(manifest_file, manifest)

    final_status = "completed"

    for file_entry in manifest["files"]:
        if file_entry.get("status") == "completed":
            continue

        if stop_event is not None and stop_event.is_set():
            final_status = "stopped"
            break

        manifest["current_file"] = file_entry["relative_path"]
        file_entry["status"] = "running"
        file_entry["started_at"] = datetime.now(UTC).isoformat()
        save_manifest(manifest_file, manifest)

        try:
            result = transcribe_media(file_entry["source_path"], profile_name=profile, model=model)
            file_entry["status"] = "completed"
            file_entry["completed_at"] = datetime.now(UTC).isoformat()
            file_entry["elapsed_seconds"] = result["elapsed_seconds"]
            file_entry["elapsed_human"] = result["elapsed_human"]
            file_entry["detected_language"] = result["language"]
            results.append(
                {
                    "source_path": result["source_path"],
                    "language": result["language"],
                    "transcript_txt": result["transcript_txt"],
                    "transcript_srt": result["transcript_srt"],
                    "transcript_json": result["transcript_json"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            file_entry["status"] = "failed"
            file_entry["completed_at"] = datetime.now(UTC).isoformat()
            file_entry["error"] = str(exc)
            final_status = "completed_with_errors"

        save_manifest(manifest_file, manifest)

    manifest["status"] = final_status
    manifest["results"] = results
    manifest["current_file"] = None
    manifest["completed_at"] = datetime.now(UTC).isoformat()
    save_manifest(manifest_file, manifest)
    return augment_manifest(manifest, manifest_path=str(manifest_file))
