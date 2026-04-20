#!/bin/zsh
set -euo pipefail

PID_FILE="/tmp/archivox-web.pid"
PORT="${ARCHIVOX_PORT:-8420}"
PID=""

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "Archivox is running on PID $PID"
    echo "Open: http://127.0.0.1:$PORT"
    exit 0
  fi
fi

PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
if [[ -n "$PID" ]]; then
  echo "$PID" >"$PID_FILE"
  echo "Archivox is running on PID $PID"
  echo "Open: http://127.0.0.1:$PORT"
  exit 0
fi

echo "Archivox is not running"
