from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import JOBS_DIR_NAME, META_DIR_NAME, SUPPORTED_MEDIA_EXTENSIONS, jobs_dir_for

PROFILE_REALTIME_FACTOR = {
    "fast": 0.20,
    "balanced": 0.45,
    "best": 0.90,
}

PROFILE_LABELS = {
    "fast": "Быстро",
    "balanced": "Сбалансированно",
    "best": "Максимально точно",
}

OUTPUT_SUMMARY = "Текст, субтитры и служебные данные"
REUSABLE_JOB_STATUSES = {"planned", "scheduled", "running", "stopping"}

JOB_STATUS_LABELS = {
    "planned": "Готов к запуску",
    "scheduled": "Запланирован",
    "running": "Идёт обработка",
    "stopping": "Останавливаем",
    "stopped": "Остановлен",
    "completed": "Готово",
    "completed_with_errors": "Готово, но есть ошибки",
}

FILE_STATUS_LABELS = {
    "planned": "Ждёт очереди",
    "running": "Обрабатывается",
    "completed": "Готово",
    "failed": "Ошибка",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def is_supported_media(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS


def iter_media_files(source_root: Path, recursive: bool) -> list[Path]:
    paths = source_root.rglob("*") if recursive else source_root.glob("*")
    media_files = []
    for path in paths:
        if META_DIR_NAME in path.parts:
            continue
        if is_supported_media(path):
            media_files.append(path)
    return sorted(media_files)


def build_output_paths(media_path: Path) -> dict[str, str]:
    stem = media_path.expanduser().resolve().with_suffix("")
    return {
        "transcript_txt": f"{stem}.transcript.txt",
        "transcript_srt": f"{stem}.transcript.srt",
        "transcript_json": f"{stem}.transcript.json",
    }


def human_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{value:.1f} {unit}"


def human_duration(total_seconds: float | None) -> str:
    if total_seconds is None:
        return "Неизвестно"

    rounded = max(int(round(total_seconds)), 0)
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours} ч")
    if minutes or hours:
        parts.append(f"{minutes} мин")
    parts.append(f"{seconds} сек")
    return " ".join(parts)


def format_local_datetime(value: str | None, *, with_seconds: bool = False) -> str | None:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value).astimezone()
    except ValueError:
        return None
    return timestamp.strftime("%d.%m.%Y %H:%M:%S" if with_seconds else "%d.%m.%Y %H:%M")


def probe_media_duration(media_path: Path) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        duration_raw = payload.get("format", {}).get("duration")
        return float(duration_raw) if duration_raw is not None else None
    except Exception:  # noqa: BLE001
        return None


def estimate_runtime_seconds(profile: str, total_duration_seconds: float | None) -> float | None:
    if total_duration_seconds is None:
        return None
    factor = PROFILE_REALTIME_FACTOR.get(profile)
    if factor is None:
        return None
    return total_duration_seconds * factor


def has_existing_transcripts(outputs: dict[str, str]) -> bool:
    return all(Path(output_path).exists() for output_path in outputs.values())


def build_file_plan(source_root: Path, media_file: Path) -> dict[str, Any]:
    outputs = build_output_paths(media_file)
    duration_seconds = probe_media_duration(media_file)
    size_bytes = media_file.stat().st_size
    existing_outputs = has_existing_transcripts(outputs)
    return {
        "source_path": str(media_file),
        "relative_path": str(media_file.relative_to(source_root)),
        "size_bytes": size_bytes,
        "size_human": human_size(size_bytes),
        "duration_seconds": duration_seconds,
        "duration_human": human_duration(duration_seconds),
        "transcript_txt": outputs["transcript_txt"],
        "transcript_srt": outputs["transcript_srt"],
        "transcript_json": outputs["transcript_json"],
        "status": "completed" if existing_outputs else "planned",
        "error": None,
        "started_at": None,
        "completed_at": datetime.fromtimestamp(
            Path(outputs["transcript_json"]).stat().st_mtime,
            tz=UTC,
        ).isoformat() if existing_outputs else None,
        "elapsed_seconds": None,
        "elapsed_human": None if not existing_outputs else "existing",
        "detected_language": None,
    }


def scan_source_path(source_path: str, recursive: bool = True, profile: str = "balanced") -> dict[str, Any]:
    source_root = Path(source_path).expanduser().resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"Path does not exist: {source_root}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {source_root}")

    media_files = iter_media_files(source_root, recursive=recursive)
    files = [build_file_plan(source_root, media_file) for media_file in media_files]

    total_size_bytes = sum(file_plan["size_bytes"] for file_plan in files)
    total_duration_seconds = sum(file_plan["duration_seconds"] or 0.0 for file_plan in files)
    pending_files = [file_plan for file_plan in files if file_plan["status"] != "completed"]
    pending_duration_seconds = sum(file_plan["duration_seconds"] or 0.0 for file_plan in pending_files)
    estimated_runtime = estimate_runtime_seconds(profile, pending_duration_seconds)

    return {
        "source_root": str(source_root),
        "recursive": recursive,
        "profile": profile,
        "file_count": len(files),
        "pending_file_count": len(pending_files),
        "total_size_bytes": total_size_bytes,
        "total_size_human": human_size(total_size_bytes),
        "total_duration_seconds": total_duration_seconds,
        "total_duration_human": human_duration(total_duration_seconds),
        "pending_duration_seconds": pending_duration_seconds,
        "pending_duration_human": human_duration(pending_duration_seconds),
        "estimated_runtime_seconds": estimated_runtime,
        "estimated_runtime_human": human_duration(estimated_runtime),
        "files": files,
    }


def build_progress(manifest: dict[str, Any]) -> dict[str, Any]:
    files = manifest.get("files", [])
    total = len(files)
    completed = sum(1 for file in files if file.get("status") == "completed")
    failed = sum(1 for file in files if file.get("status") == "failed")
    running = sum(1 for file in files if file.get("status") == "running")
    remaining = total - completed - failed - running
    progress_pct = round((completed / total) * 100, 1) if total else 0.0

    return {
        "completed_files": completed,
        "failed_files": failed,
        "running_files": running,
        "remaining_files": remaining,
        "pending_files": remaining + running,
        "progress_pct": progress_pct,
    }


def augment_manifest(manifest: dict[str, Any], manifest_path: str | None = None) -> dict[str, Any]:
    enriched = dict(manifest)
    if manifest_path:
        enriched["manifest_path"] = manifest_path
        updated_at = datetime.fromtimestamp(Path(manifest_path).stat().st_mtime).astimezone()
        enriched["updated_at"] = updated_at.isoformat()
        enriched["updated_at_display"] = updated_at.strftime("%d.%m.%Y %H:%M:%S")

    enriched["profile_label"] = PROFILE_LABELS.get(enriched.get("profile"), enriched.get("profile", ""))
    enriched["status_label"] = JOB_STATUS_LABELS.get(enriched.get("status"), enriched.get("status", ""))
    enriched["created_at_display"] = format_local_datetime(enriched.get("created_at"), with_seconds=True)
    enriched["started_at_display"] = format_local_datetime(enriched.get("started_at"))
    enriched["completed_at_display"] = format_local_datetime(enriched.get("completed_at"))

    for file_entry in enriched.get("files", []):
        file_entry["status_label"] = FILE_STATUS_LABELS.get(file_entry.get("status"), file_entry.get("status", ""))
        file_entry["output_summary"] = OUTPUT_SUMMARY

    enriched.update(build_progress(enriched))
    return enriched


def manifest_to_scan_result(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_root": manifest["source_root"],
        "recursive": manifest["recursive"],
        "profile": manifest["profile"],
        "file_count": manifest["file_count"],
        "pending_file_count": manifest.get("remaining_files", manifest.get("pending_file_count", 0)),
        "total_size_bytes": manifest["total_size_bytes"],
        "total_size_human": manifest.get("total_size_human", human_size(manifest["total_size_bytes"])),
        "total_duration_seconds": manifest.get("total_duration_seconds", 0.0),
        "total_duration_human": manifest.get(
            "total_duration_human",
            human_duration(manifest.get("total_duration_seconds", 0.0)),
        ),
        "pending_duration_seconds": manifest.get("pending_duration_seconds", 0.0),
        "pending_duration_human": manifest.get(
            "pending_duration_human",
            human_duration(manifest.get("pending_duration_seconds", 0.0)),
        ),
        "estimated_runtime_seconds": manifest.get("estimated_runtime_seconds"),
        "estimated_runtime_human": manifest.get(
            "estimated_runtime_human",
            human_duration(manifest.get("estimated_runtime_seconds")),
        ),
        "files": manifest["files"],
    }


def save_manifest(manifest_path: str | Path, manifest: dict[str, Any]) -> None:
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_manifest(manifest_path: str | Path) -> dict[str, Any]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    return augment_manifest(payload, manifest_path=str(manifest_file))


def delete_manifest(manifest_path: str | Path) -> dict[str, Any]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest does not exist: {manifest_file}")
    if manifest_file.suffix.lower() != ".json":
        raise ValueError("Only JSON job manifests can be deleted.")
    if manifest_file.parent.name != JOBS_DIR_NAME or manifest_file.parent.parent.name != META_DIR_NAME:
        raise ValueError("Refusing to delete a file outside the Archivox jobs directory.")

    manifest = read_manifest(manifest_file)
    manifest_file.unlink()
    return manifest


def files_signature(files: list[dict[str, Any]]) -> tuple[str | None, ...]:
    return tuple(file_entry.get("relative_path") for file_entry in files)


def find_reusable_job_manifest(
    scan_result: dict[str, Any],
    *,
    recursive: bool,
    profile: str,
) -> dict[str, Any] | None:
    expected_files = files_signature(scan_result["files"])
    for manifest in list_job_manifests(scan_result["source_root"]):
        if manifest.get("status") not in REUSABLE_JOB_STATUSES:
            continue
        if manifest.get("recursive") != recursive or manifest.get("profile") != profile:
            continue
        if files_signature(manifest.get("files", [])) != expected_files:
            continue
        return manifest
    return None


def create_job_manifest(
    source_path: str,
    recursive: bool,
    profile: str,
    scheduled_start_at: str | None = None,
    scan_result: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    scan_result = scan_result or scan_source_path(source_path, recursive=recursive, profile=profile)
    reusable_manifest = find_reusable_job_manifest(
        scan_result,
        recursive=recursive,
        profile=profile,
    )
    if reusable_manifest:
        if reusable_manifest.get("status") == "planned":
            manifest_path = Path(reusable_manifest["manifest_path"])
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["scheduled_start_at"] = scheduled_start_at
            save_manifest(manifest_path, manifest_payload)
            return read_manifest(reusable_manifest["manifest_path"]), True
        return reusable_manifest, True

    source_root = Path(scan_result["source_root"])
    jobs_dir = jobs_dir_for(source_root)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    manifest_path = jobs_dir / f"{job_id}.json"

    manifest = {
        "job_id": job_id,
        "created_at": utc_now_iso(),
        "started_at": None,
        "completed_at": None,
        "scheduled_start_at": scheduled_start_at,
        "status": "planned",
        "stop_requested": False,
        "current_file": None,
        "profile": profile,
        "output_mode": "same-folder",
        "source_root": scan_result["source_root"],
        "output_root": scan_result["source_root"],
        "recursive": recursive,
        "meta_dir": str(source_root / META_DIR_NAME),
        "jobs_dir": str(source_root / META_DIR_NAME / JOBS_DIR_NAME),
        "file_count": scan_result["file_count"],
        "pending_file_count": scan_result["pending_file_count"],
        "total_size_bytes": scan_result["total_size_bytes"],
        "total_size_human": scan_result["total_size_human"],
        "total_duration_seconds": scan_result["total_duration_seconds"],
        "total_duration_human": scan_result["total_duration_human"],
        "pending_duration_seconds": scan_result["pending_duration_seconds"],
        "pending_duration_human": scan_result["pending_duration_human"],
        "estimated_runtime_seconds": scan_result["estimated_runtime_seconds"],
        "estimated_runtime_human": scan_result["estimated_runtime_human"],
        "files": scan_result["files"],
    }

    save_manifest(manifest_path, manifest)
    return augment_manifest(manifest, manifest_path=str(manifest_path)), False


def list_job_manifests(source_path: str) -> list[dict[str, Any]]:
    source_root = Path(source_path).expanduser().resolve()
    jobs_dir = jobs_dir_for(source_root)
    if not jobs_dir.exists():
        return []

    manifests = []
    for manifest_file in sorted(jobs_dir.glob("*.json"), reverse=True):
        try:
            manifests.append(read_manifest(manifest_file))
        except json.JSONDecodeError:
            continue
    return manifests
