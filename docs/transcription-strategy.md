# Archivox Transcription Strategy

## Requirements

Archivox must handle:

- Ukrainian-only media;
- Russian-only media;
- mixed Ukrainian and Russian in the same archive;
- occasional mixed-language speech inside the same file.

## Primary engine choice

The leading candidate for the first real worker is `faster-whisper`.

Reasons:

- strong multilingual support;
- practical performance for local batch runs;
- active ecosystem;
- simpler mixed-language behavior than building around alignment-first tooling.

## Why not start with WhisperX as the main engine

`WhisperX` is strong for alignment and word timestamps, but its alignment step is more language-specific and less attractive as the first layer for mixed `uk` / `ru` archives.

It can still be useful later as:

- an optional timestamp refinement layer;
- a premium quality mode;
- a selective reprocessing pass.

## Recommended two-pass strategy

### Pass 1: robust archive ingestion

Use a multilingual model with:

- VAD enabled;
- no fixed language for the full archive;
- stable chunking;
- fast enough settings for overnight throughput.

Goal:

- get usable transcripts for the whole archive;
- identify hard files or low-confidence segments.

### Pass 2: targeted refinement

Only reprocess:

- files with low confidence;
- files with obvious language-switching issues;
- files that need better subtitle timing;
- files selected by the user as high value.

This keeps overnight batch time reasonable.

## Output philosophy

Archivox should not only create one transcript blob.

For each video, generate:

- `.txt` for reading and summarization;
- `.srt` for time-aligned review;
- `.json` for structured downstream use.

## Future quality controls

Later layers can add:

- confidence thresholds;
- chunk-level language hints;
- speaker diarization;
- chapter extraction;
- topic tagging;
- course/module indexing.

## Local overnight execution

Archivox should support unattended overnight runs.

Recommended macOS wrapper:

```bash
caffeinate -ism <archivox worker command>
```

That prevents idle sleep while the job is active.

## Practical product rule

Do not optimize for perfect transcription first.
Optimize for:

- folder-based reliability;
- resumability;
- mixed-language tolerance;
- usable outputs by morning.

