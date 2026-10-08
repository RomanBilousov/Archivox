# Archivox

[English README](README.en.md)

Local-first приложение для пакетной транскрибации больших локальных архивов без обязательной загрузки файлов в облако.

## Текущее состояние

Фактическая сверка: 2026-10-08. Базовая ветка: `main`. Source commit: `20ad4694a3befe831e891e7f1e23e9e8200cbb56`.

Существующая документация подтверждает:
- локальный web UI на FastAPI;
- `faster-whisper`;
- рекурсивный scan локальных media-файлов;
- resumable jobs;
- выходы `.txt`, `.srt`, `.json` рядом с исходным media;
- optional macOS background/launcher helpers.

## Ручной запуск

Требования из README: Python 3.12+ и `uv`.

```bash
uv sync
uv run archivox
```

Локальный UI указан как `http://127.0.0.1:8420`.

## Установка

В английском README описан one-command installer через удалённый shell script. Перед использованием команды вида `curl ... | bash` рекомендуется сначала прочитать актуальный `scripts/install.sh` и проверить source SHA/назначение.

## Документация

- [English README](README.en.md)
- [Product brief](docs/product.md)
- [Architecture](docs/architecture.md)

## Управление проектом

GitHub Projects — единственный рабочий трекер. Конкретный Project в текущей сверке не подтверждён.

## Приватность

Archivox предназначен для локальных архивов. Не добавляйте в репозиторий транскрипты приватных библиотек, исходные медиа или локальные job metadata.
