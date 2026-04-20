from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.jobs import read_manifest, save_manifest
from app.transcribe import run_job_manifest


@dataclass
class JobController:
    manifest_path: str
    thread: threading.Thread
    stop_event: threading.Event


RUNNERS: dict[str, JobController] = {}
RUNNERS_LOCK = threading.Lock()
ACTIVE_JOB_STATUSES = {"scheduled", "running", "stopping"}


def _normalize_manifest_path(manifest_path: str | Path) -> str:
    return str(Path(manifest_path).expanduser().resolve())


def _runner_main(manifest_path: str, stop_event: threading.Event, scheduled_start_at: datetime | None) -> None:
    try:
        manifest = read_manifest(manifest_path)
        manifest["stop_requested"] = False
        if scheduled_start_at is None:
            manifest["scheduled_start_at"] = None
        save_manifest(manifest_path, manifest)

        if scheduled_start_at is not None:
            manifest["status"] = "scheduled"
            manifest["scheduled_start_at"] = scheduled_start_at.isoformat(timespec="minutes")
            save_manifest(manifest_path, manifest)

            while datetime.now() < scheduled_start_at:
                if stop_event.is_set():
                    manifest = read_manifest(manifest_path)
                    manifest["status"] = "stopped"
                    manifest["stop_requested"] = True
                    save_manifest(manifest_path, manifest)
                    return
                time.sleep(1)

        if stop_event.is_set():
            manifest = read_manifest(manifest_path)
            manifest["status"] = "stopped"
            manifest["stop_requested"] = True
            save_manifest(manifest_path, manifest)
            return

        run_job_manifest(manifest_path, stop_event=stop_event)
    finally:
        with RUNNERS_LOCK:
            RUNNERS.pop(manifest_path, None)


def start_job_background(manifest_path: str | Path, scheduled_start_at: datetime | None = None) -> None:
    normalized = _normalize_manifest_path(manifest_path)
    with RUNNERS_LOCK:
        existing = RUNNERS.get(normalized)
        if existing and existing.thread.is_alive():
            raise RuntimeError("This job is already active.")

        stop_event = threading.Event()
        thread = threading.Thread(
            target=_runner_main,
            args=(normalized, stop_event, scheduled_start_at),
            name=f"archivox-job-{Path(normalized).stem}",
            daemon=True,
        )
        RUNNERS[normalized] = JobController(
            manifest_path=normalized,
            thread=thread,
            stop_event=stop_event,
        )
        thread.start()


def stop_job_background(manifest_path: str | Path) -> bool:
    normalized = _normalize_manifest_path(manifest_path)
    with RUNNERS_LOCK:
        controller = RUNNERS.get(normalized)
        if controller is None:
            return False
        controller.stop_event.set()

    manifest = read_manifest(normalized)
    manifest["stop_requested"] = True
    if manifest["status"] in {"running", "scheduled"}:
        manifest["status"] = "stopping"
    save_manifest(normalized, manifest)
    return True


def is_job_active(manifest_path: str | Path) -> bool:
    normalized = _normalize_manifest_path(manifest_path)
    with RUNNERS_LOCK:
        controller = RUNNERS.get(normalized)
        return bool(controller and controller.thread.is_alive())


def reconcile_job_runtime(manifest_path: str | Path) -> tuple[dict, bool]:
    normalized = _normalize_manifest_path(manifest_path)
    manifest = read_manifest(normalized)
    if manifest.get("status") not in ACTIVE_JOB_STATUSES:
        return manifest, False
    if is_job_active(normalized):
        return manifest, False

    manifest["status"] = "stopped"
    manifest["stop_requested"] = True
    manifest["current_file"] = None

    for file_entry in manifest.get("files", []):
        if file_entry.get("status") == "running":
            file_entry["status"] = "planned"
            file_entry["started_at"] = None

    save_manifest(normalized, manifest)
    return read_manifest(normalized), True
