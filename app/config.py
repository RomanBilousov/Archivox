from pathlib import Path

APP_NAME = "Archivox"
APP_HOST = "127.0.0.1"
APP_PORT = 8420

SUPPORTED_MEDIA_EXTENSIONS = {
    ".mp3",
    ".mp4",
    ".m4a",
    ".m4v",
    ".mov",
    ".mkv",
    ".wav",
    ".webm",
    ".aac",
    ".flac",
}

META_DIR_NAME = ".archivox"
JOBS_DIR_NAME = "jobs"


def meta_dir_for(source_root: Path) -> Path:
    return source_root / META_DIR_NAME


def jobs_dir_for(source_root: Path) -> Path:
    return meta_dir_for(source_root) / JOBS_DIR_NAME

