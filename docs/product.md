# Archivox Product Brief

## One-liner

Archivox turns long-form media archives into usable transcript assets and searchable knowledge, without requiring cloud upload.

## Core problem

Teams buy expensive courses, collect internal trainings, record calls, and save client videos, but almost none of that media becomes operational knowledge because:

- content is too long to rewatch;
- useful ideas are buried inside hours of video;
- mixed-language content is annoying to process manually;
- cloud transcription is expensive, slow, or sensitive;
- current tools are optimized for single files, not folder-based archives.

## Initial user

Founder-led small teams, agencies, consultants, and operators with:

- large local folders of videos;
- mixed Ukrainian and Russian speech;
- a need to batch-process media overnight;
- a preference for keeping source files local.

## Core value promise

Archivox gives the user a local “folder in, transcript out” workflow:

- one folder input;
- one overnight batch;
- one transcript set per video;
- one hidden metadata folder for resuming and tracking jobs.

## MVP scope

### In scope

- path-based folder selection;
- recursive media scan;
- job planning;
- transcript output strategy;
- quality profiles;
- resumable job manifests;
- local web UI.

### Out of scope for the first cut

- multi-user auth;
- hosted SaaS deployment;
- billing;
- cloud storage sync;
- perfect speaker diarization;
- knowledge graph automation.

## Main user flow

1. User enters a folder path.
2. Archivox scans for supported media.
3. User chooses:
   - recursive or single folder;
   - quality profile;
   - output mode.
4. Archivox creates a job manifest.
5. Worker processes files one by one.
6. Archivox writes transcript files next to source media.
7. User later searches, summarizes, or exports results.

## Output conventions

Given:

`/Volumes/Courses/Module 1/lesson-01.mp4`

Archivox should eventually write:

- `/Volumes/Courses/Module 1/lesson-01.transcript.txt`
- `/Volumes/Courses/Module 1/lesson-01.transcript.srt`
- `/Volumes/Courses/Module 1/lesson-01.transcript.json`

And service metadata:

- `/Volumes/Courses/.archivox/jobs/<job-id>.json`
- `/Volumes/Courses/.archivox/logs/...`

## Commercial potential

Archivox can evolve from an internal operator tool into:

- a desktop utility for agencies and founders;
- a local-first pro app for private archives;
- a hosted B2B ingestion and knowledge indexing product.

The local-first MVP is still the right place to start because it validates the real workflow cheaply.

