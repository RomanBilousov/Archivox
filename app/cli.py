from __future__ import annotations

import argparse
import json

from app.transcribe import run_job_manifest, transcribe_file


def transcribe_file_main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe a single media file with Archivox.")
    parser.add_argument("media_path", help="Absolute or relative path to the media file.")
    parser.add_argument(
        "--profile",
        default="balanced",
        choices=["fast", "balanced", "best"],
        help="Transcription quality profile.",
    )
    args = parser.parse_args()

    result = transcribe_file(args.media_path, profile_name=args.profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_job_main() -> None:
    parser = argparse.ArgumentParser(description="Run an Archivox job manifest.")
    parser.add_argument("manifest_path", help="Path to a .archivox job manifest JSON file.")
    args = parser.parse_args()

    result = run_job_manifest(args.manifest_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
