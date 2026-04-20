# Archivox Architecture

## Design principle

Archivox is a local-first batch system with a thin local web interface.

The browser is only used for control.
The filesystem work happens on the machine that owns the media.

## Why not browser upload

For this product, browser-only folder upload is the wrong primitive:

- it copies large media files into a web request path;
- it behaves badly for external SSD workflows;
- it adds unnecessary I/O and browser constraints;
- it makes resumable batch execution harder.

The MVP therefore uses a backend path input instead of a browser file uploader.

## System components

### 1. Web UI

Responsibilities:

- accept source folder path;
- preview supported files;
- configure job profile;
- create jobs;
- show progress, remaining files, and current file;
- start immediately or schedule later;
- stop gracefully after the current file.

### 2. Job planner

Responsibilities:

- validate source path;
- scan media files;
- build deterministic output paths;
- write a job manifest to `.archivox/jobs/`.

### 3. Worker

Implemented as a reusable transcription layer, exposed through both CLI entrypoints and the web UI runner.

Responsibilities:

- load job manifest;
- run transcription file by file;
- write transcript outputs;
- checkpoint progress;
- resume interrupted jobs;
- skip files that already have transcript outputs.

### 4. Transcript post-processing

Future component.

Responsibilities:

- normalize punctuation;
- generate subtitle output;
- create searchable JSON;
- optionally build summaries or note exports.

## Data model

### Source folder

The folder selected by the user.

Example:

`/Volumes/Media/KnB`

### Metadata folder

A hidden Archivox workspace inside the source root:

`/Volumes/Media/KnB/.archivox`

This should contain:

- `jobs/`
- future caches and indexes.

### File outputs

Outputs live next to the original media file by default because that is the simplest mental model for the user.

## Job manifest

Each job manifest should contain:

- job id;
- created timestamp;
- source root;
- recursive flag;
- quality profile;
- status;
- file list;
- target transcript paths.

This makes the system resumable and keeps the worker stateless enough to recover after interruption.

## Profiles

The UI should expose profiles, not raw model names.

Recommended profiles:

- `fast`
- `balanced`
- `best`

Internally these can later map to:

- model family;
- compute type;
- chunk size;
- optional alignment;
- optional VAD behavior.

## Language strategy

Mixed `uk` / `ru` content is a first-class requirement.

The implementation should:

- use a multilingual base model;
- avoid forcing one language for the whole archive;
- allow chunk-level or file-level language detection;
- support reprocessing low-confidence segments later.

See [transcription-strategy.md](transcription-strategy.md).
