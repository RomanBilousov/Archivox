from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import APP_HOST, APP_NAME, APP_PORT
from app.jobs import (
    OUTPUT_SUMMARY,
    create_job_manifest,
    delete_manifest,
    list_job_manifests,
    manifest_to_scan_result,
    read_manifest,
    scan_source_path,
)
from app.runner import (
    is_job_active,
    reconcile_job_runtime,
    start_job_background,
    stop_job_background,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

PROFILE_LABELS = {
    "fast": "Быстро",
    "balanced": "Сбалансированно",
    "best": "Максимально точно",
}

STATUS_LABELS = {
    "planned": "Готов к запуску",
    "scheduled": "Запланирован",
    "running": "Идёт обработка",
    "stopping": "Останавливаем после текущего видео",
    "stopped": "Остановлен",
    "completed": "Готово",
    "completed_with_errors": "Готово, но есть ошибки",
}


def pick_folder_via_macos_dialog(source_path: str = "") -> str:
    default_location_line = ""
    normalized = source_path.strip()
    if normalized:
        candidate = Path(normalized).expanduser()
        if candidate.exists():
            folder = candidate if candidate.is_dir() else candidate.parent
            escaped = str(folder.resolve()).replace("\\", "\\\\").replace('"', '\\"')
            default_location_line = f'default location (POSIX file "{escaped}") '

    script = (
        'set chosenFolder to choose folder '
        f'with prompt "Выберите папку с видео для Archivox" {default_location_line}\n'
        "POSIX path of chosenFolder"
    )

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "User canceled" in stderr:
            raise RuntimeError("Выбор папки отменён.")
        raise RuntimeError(stderr or "Не удалось открыть системное окно выбора папки.")

    chosen = result.stdout.strip()
    if not chosen:
        raise RuntimeError("Не удалось получить путь к выбранной папке.")
    return chosen


def describe_job_status(status: str, *, is_active: bool = False) -> str:
    if is_active:
        return "Идёт обработка"
    return STATUS_LABELS.get(status, status)


def describe_job_message(job: dict, *, is_active: bool = False) -> str:
    if is_active and job.get("current_file"):
        return (
            "Archivox сейчас обрабатывает видео и сохранит результат рядом с исходным файлом. "
            "Закрывать эту страницу можно."
        )
    if job.get("status") == "planned":
        return "Запуск подготовлен. Можно начать сейчас или выбрать время позже."
    if job.get("status") == "scheduled":
        return "Запуск поставлен в очередь и начнётся в указанное время."
    if job.get("status") == "stopping":
        return "Archivox завершит текущее видео и затем остановится."
    if job.get("status") == "stopped":
        return "Обработка остановлена. Можно продолжить с того места, где Archivox остановился."
    if job.get("status") == "completed":
        return "Все видео из этого плана уже обработаны."
    if job.get("status") == "completed_with_errors":
        return "Основная обработка завершена, но часть файлов требует внимания."
    return "Здесь видно текущее состояние запуска."


def missing_job_message() -> str:
    return (
        "Этот план запуска не найден. Возможно, его удалили или внешний диск сейчас не подключён."
    )


def describe_user_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "Папка не найдена. Проверьте путь и убедитесь, что диск подключён."
    if isinstance(exc, NotADirectoryError):
        return "Нужно выбрать именно папку с видео, а не отдельный файл."
    return str(exc)


def build_return_url(
    *,
    manifest_path: str | None = None,
    source_path: str = "",
    notice: str | None = None,
    error: str | None = None,
) -> str:
    if manifest_path:
        normalized_manifest = str(Path(manifest_path).expanduser().resolve())
        params = {"manifest_path": normalized_manifest}
        if notice:
            params["notice"] = notice
        if error:
            params["error"] = error
        return f"/jobs/view?{urlencode(params)}"

    params: dict[str, str] = {}
    if source_path:
        params["source_path"] = str(Path(source_path).expanduser().resolve())
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    return f"/?{urlencode(params)}" if params else "/"


def open_path_in_finder(target_path: str) -> None:
    target = Path(target_path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    finder_target = target if target.is_dir() else target.parent
    subprocess.run(["open", str(finder_target)], check=True)


def next_pending_file(job: dict) -> str | None:
    for file_entry in job.get("files", []):
        if file_entry.get("status") in {"running", "planned"}:
            return file_entry.get("relative_path")
    return None


def describe_notice(notice: str | None) -> tuple[str, str]:
    if not notice:
        return "success", "Готово"
    if "перезапущен" in notice:
        return "info", "Важно"
    if "вместо создания дубля" in notice:
        return "info", "Без дублей"
    return "success", "Готово"


def enrich_job_view(job: dict, *, is_active: bool = False) -> dict:
    next_file = next_pending_file(job)
    completed = job.get("completed_files", 0)
    total = job.get("file_count", 0)
    current_file = job.get("current_file")
    status = job.get("status")

    if is_active:
        job["view_mode"] = "live"
        job["view_heading"] = "Archivox работает"
        job["view_summary"] = (
            f"Сейчас обрабатывается {current_file}. Страницу можно закрыть."
            if current_file
            else "Обработка уже идёт. Archivox сам перейдёт к следующему файлу."
        )
        job["focus_label"] = "Текущее видео"
        job["focus_value"] = current_file or next_file or "Обработка уже запущена"
        job["action_eyebrow"] = "Если нужно остановить"
        job["action_heading"] = "Archivox завершит текущее видео"
        job["action_summary"] = "После этого он остановится и не возьмёт следующее."
        job["action_mode"] = "stop"
        job["view_hint"] = (
            "Пока первое длинное видео не закончится, число готовых файлов может не меняться — это нормально."
            if completed == 0
            else None
        )
        return job

    if status in {"planned", "stopped"}:
        job["view_mode"] = "ready"
        job["view_heading"] = "Можно продолжить"
        if next_file:
            job["view_summary"] = (
                f"Готово {completed} из {total}. Следующим будет {next_file}."
            )
        else:
            job["view_summary"] = "Запуск подготовлен и может стартовать в любой момент."
        job["focus_label"] = "Следующее видео"
        job["focus_value"] = next_file or "Все файлы уже обработаны"
        job["action_eyebrow"] = "Следующий шаг"
        job["action_heading"] = "Продолжить обработку"
        job["action_summary"] = "Можно начать сразу или поставить запуск в очередь на позже."
        job["action_mode"] = "start"
        job["view_hint"] = None
        return job

    if status == "completed":
        job["view_mode"] = "done"
        job["view_heading"] = "Все готово"
        job["view_summary"] = "Все видео обработаны. Результаты уже лежат рядом с исходными файлами."
        job["focus_label"] = "Обработано"
        job["focus_value"] = f"{completed} из {total} видео"
        job["action_eyebrow"] = "Что дальше"
        job["action_heading"] = "Открыть результаты"
        job["action_summary"] = "Можно перейти к папке с файлами или выбрать другую папку для нового запуска."
        job["action_mode"] = "done"
        job["view_hint"] = None
        return job

    if status == "completed_with_errors":
        failed = job.get("failed_files", 0)
        job["view_mode"] = "warning"
        job["view_heading"] = "Почти готово"
        job["view_summary"] = (
            f"Обработано {completed} из {total}. Ещё {failed} файл(ов) требуют внимания."
        )
        job["focus_label"] = "Требуют внимания"
        job["focus_value"] = f"{failed} файл(ов)"
        job["action_eyebrow"] = "Что дальше"
        job["action_heading"] = "Проверить результаты"
        job["action_summary"] = "Откройте папку с видео и посмотрите, какие файлы нужно запустить ещё раз."
        job["action_mode"] = "done"
        job["view_hint"] = None
        return job

    job["view_mode"] = "idle"
    job["view_heading"] = job.get("status_label", "Состояние запуска")
    job["view_summary"] = job.get("status_message", "Здесь видно текущее состояние запуска.")
    job["focus_label"] = "Следующее видео"
    job["focus_value"] = next_file or current_file or "Нет данных"
    job["action_eyebrow"] = "Следующий шаг"
    job["action_heading"] = "Продолжить"
    job["action_summary"] = "Можно продолжить работу с этим запуском."
    job["action_mode"] = "start"
    job["view_hint"] = None
    return job


def render_home(
    request: Request,
    *,
    source_path: str = "",
    recursive: bool = True,
    profile: str = "balanced",
    scheduled_start_at: str = "",
    scan_result: dict | None = None,
    job_manifest: dict | None = None,
    notice: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    recovery_notice = notice
    notice_variant, notice_title = describe_notice(recovery_notice)

    if job_manifest and job_manifest.get("manifest_path"):
        job_manifest, reconciled = reconcile_job_runtime(job_manifest["manifest_path"])
        if reconciled and not recovery_notice:
            recovery_notice = (
                "Archivox был перезапущен во время обработки. "
                "План автоматически переведён в безопасное состояние. Теперь его можно запустить заново."
            )
        notice_variant, notice_title = describe_notice(recovery_notice)

    effective_source = source_path or (job_manifest["source_root"] if job_manifest else "")
    recent_jobs = list_job_manifests(effective_source) if effective_source else []
    normalized_recent_jobs = []
    for job in recent_jobs:
        if job.get("manifest_path"):
            job, _ = reconcile_job_runtime(job["manifest_path"])
        job["is_active"] = is_job_active(job["manifest_path"])
        job["status_label"] = describe_job_status(job["status"], is_active=job["is_active"])
        job["status_message"] = describe_job_message(job, is_active=job["is_active"])
        job["run_label"] = job.get("created_at_display") or job["job_id"]
        job["profile_label"] = PROFILE_LABELS.get(job["profile"], job["profile"])
        normalized_recent_jobs.append(job)
    history_jobs = normalized_recent_jobs
    if job_manifest:
        current_manifest_path = str(Path(job_manifest["manifest_path"]).expanduser().resolve())
        history_jobs = [
            job for job in normalized_recent_jobs
            if str(Path(job["manifest_path"]).expanduser().resolve()) != current_manifest_path
        ]

    preview_source = job_manifest["files"] if job_manifest else (scan_result["files"] if scan_result else [])
    preview_files = preview_source[:50]
    for file_entry in preview_files:
        file_entry["output_summary"] = OUTPUT_SUMMARY
    auto_refresh = bool(job_manifest and job_manifest["status"] in {"scheduled", "running", "stopping"})
    auto_refresh_url = (
        f"/jobs/view?manifest_path={quote(job_manifest['manifest_path'])}"
        if job_manifest
        else ""
    )
    job_is_active = bool(job_manifest and is_job_active(job_manifest["manifest_path"]))

    if job_manifest:
        job_manifest["is_active"] = job_is_active
        job_manifest["status_label"] = describe_job_status(job_manifest["status"], is_active=job_is_active)
        job_manifest["status_message"] = describe_job_message(job_manifest, is_active=job_is_active)
        job_manifest["run_label"] = job_manifest.get("created_at_display") or job_manifest["job_id"]
        job_manifest["profile_label"] = PROFILE_LABELS.get(job_manifest["profile"], job_manifest["profile"])
        job_manifest = enrich_job_view(job_manifest, is_active=job_is_active)

    planner_source_path = "" if job_manifest else effective_source
    planner_scheduled_start_at = "" if job_manifest else scheduled_start_at

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": APP_NAME,
            "source_path": effective_source,
            "planner_source_path": planner_source_path,
            "recursive": recursive,
            "profile": profile,
            "scheduled_start_at": scheduled_start_at or ((job_manifest.get("scheduled_start_at") or "") if job_manifest else ""),
            "planner_scheduled_start_at": planner_scheduled_start_at,
            "scan_result": scan_result,
            "preview_files": preview_files,
            "job_manifest": job_manifest,
            "history_jobs": history_jobs[:5],
            "auto_refresh": auto_refresh,
            "auto_refresh_url": auto_refresh_url,
            "job_is_active": job_is_active,
            "notice": recovery_notice,
            "notice_variant": notice_variant,
            "notice_title": notice_title,
            "error": error,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    manifest_path: str | None = None,
    source_path: str = "",
    notice: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    if manifest_path:
        try:
            manifest = read_manifest(manifest_path)
        except FileNotFoundError:
            return render_home(request, source_path=source_path, error=missing_job_message())
        return render_home(
            request,
            source_path=manifest["source_root"],
            recursive=manifest["recursive"],
            profile=manifest["profile"],
            scheduled_start_at=manifest.get("scheduled_start_at") or "",
            scan_result=manifest_to_scan_result(manifest),
            job_manifest=manifest,
            notice=notice,
            error=error,
        )
    normalized_source = str(Path(source_path).expanduser().resolve()) if source_path else ""
    return render_home(request, source_path=normalized_source, notice=notice, error=error)


@app.get("/jobs/view", response_class=HTMLResponse)
async def view_job(
    request: Request,
    manifest_path: str,
    notice: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    try:
        manifest = read_manifest(manifest_path)
    except FileNotFoundError:
        return render_home(request, error=missing_job_message())
    return render_home(
        request,
        source_path=manifest["source_root"],
        recursive=manifest["recursive"],
        profile=manifest["profile"],
        scheduled_start_at=manifest.get("scheduled_start_at") or "",
        scan_result=manifest_to_scan_result(manifest),
        job_manifest=manifest,
        notice=notice,
        error=error,
    )


@app.post("/scan", response_class=HTMLResponse)
async def scan(
    request: Request,
    source_path: str = Form(...),
    recursive: str | None = Form(default=None),
    profile: str = Form(default="balanced"),
    scheduled_start_at: str = Form(default=""),
) -> HTMLResponse:
    recursive_flag = recursive == "on"
    try:
        scan_result = scan_source_path(source_path, recursive=recursive_flag, profile=profile)
        return render_home(
            request,
            source_path=source_path,
            recursive=recursive_flag,
            profile=profile,
            scheduled_start_at=scheduled_start_at,
            scan_result=scan_result,
        )
    except Exception as exc:  # noqa: BLE001
        return render_home(
            request,
            source_path=source_path,
            recursive=recursive_flag,
            profile=profile,
            scheduled_start_at=scheduled_start_at,
            error=describe_user_error(exc),
        )


@app.post("/pick-folder")
async def pick_folder(source_path: str = Form(default="")) -> JSONResponse:
    try:
        chosen = pick_folder_via_macos_dialog(source_path)
        return JSONResponse({"ok": True, "source_path": chosen})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )


@app.post("/open-path")
async def open_path(
    target_path: str = Form(...),
    manifest_path: str = Form(default=""),
    source_path: str = Form(default=""),
) -> RedirectResponse:
    try:
        open_path_in_finder(target_path)
        return RedirectResponse(
            url=build_return_url(
                manifest_path=manifest_path or None,
                source_path=source_path,
            ),
            status_code=303,
        )
    except Exception as exc:  # noqa: BLE001
        return RedirectResponse(
            url=build_return_url(
                manifest_path=manifest_path or None,
                source_path=source_path,
                error=describe_user_error(exc),
            ),
            status_code=303,
        )


@app.post("/jobs", response_class=HTMLResponse)
async def create_job(
    request: Request,
    source_path: str = Form(...),
    recursive: str | None = Form(default=None),
    profile: str = Form(default="balanced"),
    scheduled_start_at: str = Form(default=""),
) -> HTMLResponse:
    recursive_flag = recursive == "on"
    try:
        scan_result = scan_source_path(source_path, recursive=recursive_flag, profile=profile)
        job_manifest, reused_existing = create_job_manifest(
            source_path,
            recursive=recursive_flag,
            profile=profile,
            scheduled_start_at=scheduled_start_at or None,
            scan_result=scan_result,
        )
        return render_home(
            request,
            source_path=source_path,
            recursive=recursive_flag,
            profile=profile,
            scheduled_start_at=scheduled_start_at,
            scan_result=scan_result,
            job_manifest=job_manifest,
            notice=(
                "Для этой папки уже есть незавершённый запуск. "
                "Открываю его вместо создания дубля."
                if reused_existing
                else None
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return render_home(
            request,
            source_path=source_path,
            recursive=recursive_flag,
            profile=profile,
            scheduled_start_at=scheduled_start_at,
            error=describe_user_error(exc),
        )


@app.post("/jobs/start")
async def start_job(
    manifest_path: str = Form(...),
    scheduled_start_at: str = Form(default=""),
) -> RedirectResponse:
    try:
        read_manifest(manifest_path)
    except FileNotFoundError:
        return RedirectResponse(url=f"/?error={quote(missing_job_message())}", status_code=303)
    scheduled_time = datetime.fromisoformat(scheduled_start_at) if scheduled_start_at else None
    start_job_background(manifest_path, scheduled_start_at=scheduled_time)
    normalized = str(Path(manifest_path).expanduser().resolve())
    return RedirectResponse(
        url=f"/jobs/view?manifest_path={quote(normalized)}",
        status_code=303,
    )


@app.post("/jobs/stop")
async def stop_job(manifest_path: str = Form(...)) -> RedirectResponse:
    try:
        read_manifest(manifest_path)
    except FileNotFoundError:
        return RedirectResponse(url=f"/?error={quote(missing_job_message())}", status_code=303)
    stop_job_background(manifest_path)
    normalized = str(Path(manifest_path).expanduser().resolve())
    return RedirectResponse(
        url=f"/jobs/view?manifest_path={quote(normalized)}",
        status_code=303,
    )


@app.post("/jobs/delete")
async def delete_job(manifest_path: str = Form(...)) -> RedirectResponse:
    try:
        manifest = read_manifest(manifest_path)
    except FileNotFoundError:
        return RedirectResponse(url=f"/?error={quote(missing_job_message())}", status_code=303)
    normalized = manifest["manifest_path"]

    if is_job_active(normalized):
        return RedirectResponse(
            url=(
                f"/jobs/view?manifest_path={quote(normalized)}"
                f"&error={quote('Сначала остановите обработку, а потом удаляйте этот запуск.')}"
            ),
            status_code=303,
        )

    deleted_label = manifest.get("created_at_display") or manifest["job_id"]
    delete_manifest(normalized)
    return RedirectResponse(
        url=(
            f"/?source_path={quote(manifest['source_root'])}"
            f"&notice={quote(f'Запуск удалён: {deleted_label}.')}"
        ),
        status_code=303,
    )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=False)
