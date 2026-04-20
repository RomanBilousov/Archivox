#!/bin/zsh
set -euo pipefail

PID_FILE="/tmp/archivox-web.pid"
PORT="${ARCHIVOX_PORT:-8420}"

PID=""
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
elif lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN | head -n 1)"
fi

if [[ -z "$PID" ]]; then
  echo "Archivox is not running"
  exit 0
fi

if kill -0 "$PID" >/dev/null 2>&1; then
  kill "$PID"
  for _ in {1..10}; do
    if ! kill -0 "$PID" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  if kill -0 "$PID" >/dev/null 2>&1; then
    kill -9 "$PID" >/dev/null 2>&1 || true
  fi
  echo "Stopped Archivox PID $PID"
else
  echo "Archivox PID file existed, but process was already gone"
fi

rm -f "$PID_FILE"
