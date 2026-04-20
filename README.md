# Archivox

Archivox is a local-first media transcription tool for long-form video archives,
course libraries, internal trainings, and private media folders.

## One-command install

Install Archivox, set up dependencies, start the local web app, and open it in
your browser:

```bash
curl -fsSL https://raw.githubusercontent.com/RomanBilousov/Archivox/main/scripts/install.sh | bash
```

What this does:

- installs `uv` if it is missing
- clones or updates the repo in a sensible local app directory
- runs `uv sync`
- starts Archivox in the background
- opens `http://127.0.0.1:8420`

Useful variants:

```bash
# Install but do not start
curl -fsSL https://raw.githubusercontent.com/RomanBilousov/Archivox/main/scripts/install.sh | ARCHIVOX_START_MODE=none bash

# Install and keep it in a custom folder
curl -fsSL https://raw.githubusercontent.com/RomanBilousov/Archivox/main/scripts/install.sh | ARCHIVOX_INSTALL_DIR="$HOME/Archivox" bash

# Install and also create the macOS launcher app
curl -fsSL https://raw.githubusercontent.com/RomanBilousov/Archivox/main/scripts/install.sh | ARCHIVOX_INSTALL_LAUNCHER_APP=1 bash
```

The workflow is simple:

- choose a local folder or external drive path;
- scan supported audio and video files;
- create a resumable batch job;
- write transcript files next to the source media;
- keep service metadata inside a hidden `.archivox/` folder.

## Why it exists

Most transcription tools are optimized for one file at a time or for cloud
upload. Archivox is designed for operators who already have large local media
folders and want a practical `folder in, transcript out` workflow without
uploading everything first.

This is useful when:

- the archive is large and lives on an external SSD;
- privacy matters;
- mixed-language content needs to be processed overnight;
- transcripts should stay next to the original files.

## What it does today

- local web UI powered by `FastAPI`
- recursive media scan for supported file types
- resumable job manifests stored in `.archivox/jobs/`
- batch transcription with `faster-whisper`
- transcript outputs in `txt`, `srt`, and `json`
- graceful stop after the current file
- optional macOS launch scripts for background use

## Output model

Given a source file like:

```text
/Volumes/Courses/Module 1/lesson-01.mp4
```

Archivox writes:

- `lesson-01.transcript.txt`
- `lesson-01.transcript.srt`
- `lesson-01.transcript.json`

Service metadata is stored under:

```text
/Volumes/Courses/.archivox/jobs/<job-id>.json
```

## Requirements

- Python `3.12+`
- [`uv`](https://docs.astral.sh/uv/)
- enough local disk space for generated transcripts and model downloads

## Getting started

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Start the local web app:

   ```bash
   uv run archivox
   ```

3. Open `http://127.0.0.1:8420`
4. Select or paste a folder path
5. Scan the folder and create a job

If you already cloned the repo manually and just want the same local setup flow:

```bash
./scripts/install.sh
```

## CLI usage

Transcribe a single file:

```bash
uv run archivox-transcribe "/absolute/path/to/video.mp4" --profile fast
```

Run a planned job manifest:

```bash
uv run archivox-run-job "/absolute/path/to/.archivox/jobs/<job-id>.json"
```

Available profiles:

- `fast`
- `balanced`
- `best`

## Overnight usage

If you want the machine to stay awake during a long run:

```bash
caffeinate -dimsu uv run archivox
```

Or for a planned manifest:

```bash
caffeinate -ism uv run archivox-run-job "/absolute/path/to/.archivox/jobs/<job-id>.json"
```

## macOS helpers

Archivox includes optional scripts for background usage on macOS.

Start the web app in the background:

```bash
chmod +x scripts/*.sh
./scripts/start_background.sh
```

Check status:

```bash
./scripts/status_background.sh
```

Stop it:

```bash
./scripts/stop_background.sh
```

Install a LaunchAgent:

```bash
chmod +x scripts/*.sh
./scripts/install_launch_agent.sh
```

Uninstall it:

```bash
./scripts/uninstall_launch_agent.sh
```

Install a clickable macOS app wrapper:

```bash
chmod +x scripts/*.sh
./scripts/install_launcher_app.sh
```

This creates `~/Applications/Archivox.app`. If you move the repository later,
run the installer again so the launcher and LaunchAgent point to the new path.

## Project structure

```text
Archivox/
├── app/                     # web app, job planning, transcription runtime
├── docs/                    # product and architecture notes
├── ops/macos/               # LaunchAgent template
├── scripts/                 # local start/stop/install helpers
├── pyproject.toml
└── README.md
```

## Notes

- transcript files are written next to the source media, not into a separate export folder
- hidden runtime metadata stays inside `.archivox/`
- this repository contains application code and helper scripts, not private media or runtime jobs

Logs:

- `/tmp/archivox-web.out.log`
- `/tmp/archivox-web.err.log`

Note: if the repository stays inside `Documents`, macOS privacy rules may block the LaunchAgent from starting reliably. In that case, prefer the background scripts above.

## What the next step should do

The next implementation milestone after this worker is:

- add an explicit `force re-run` toggle for already-transcribed files;
- add per-job elapsed time and ETA in the UI;
- optionally summarize transcripts into reusable knowledge notes.

See [docs/product.md](docs/product.md), [docs/architecture.md](docs/architecture.md), and [docs/transcription-strategy.md](docs/transcription-strategy.md).
