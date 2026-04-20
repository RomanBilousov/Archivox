#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
find_uv_bin() {
  local candidates=(
    "${UV_BIN:-}"
    "$(command -v uv 2>/dev/null || true)"
    "$HOME/.local/bin/uv"
    "/opt/homebrew/bin/uv"
    "/usr/local/bin/uv"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

UV_BIN="$(find_uv_bin)" || {
  echo "uv binary not found. Install uv first or pass UV_BIN=/absolute/path/to/uv." >&2
  exit 1
}
PID_FILE="/tmp/archivox-web.pid"
OUT_LOG="/tmp/archivox-web.out.log"
ERR_LOG="/tmp/archivox-web.err.log"
PORT="${ARCHIVOX_PORT:-8420}"

if [[ -f "$PID_FILE" ]]; then
  PID_IN_FILE="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$PID_IN_FILE" ]] && ! kill -0 "$PID_IN_FILE" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
  fi
fi

LISTENER_PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
if [[ -n "$LISTENER_PID" ]]; then
  echo "Archivox is already running on PID $LISTENER_PID"
  echo "$LISTENER_PID" >"$PID_FILE"
  exit 0
fi

LAUNCH_PID="$(
ROOT_DIR="$ROOT_DIR" UV_BIN="$UV_BIN" OUT_LOG="$OUT_LOG" ERR_LOG="$ERR_LOG" python3 - <<'PY'
import os
import subprocess

root_dir = os.environ["ROOT_DIR"]
uv_bin = os.environ["UV_BIN"]
out_log = os.environ["OUT_LOG"]
err_log = os.environ["ERR_LOG"]

with open(os.devnull, "rb") as stdin_f, open(out_log, "ab") as stdout_f, open(err_log, "ab") as stderr_f:
    process = subprocess.Popen(
        [uv_bin, "run", "archivox"],
        cwd=root_dir,
        stdin=stdin_f,
        stdout=stdout_f,
        stderr=stderr_f,
        start_new_session=True,
    )

print(process.pid)
PY
)"

for _ in {1..20}; do
  LISTENER_PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [[ -n "$LISTENER_PID" ]] && curl -sSf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    echo "$LISTENER_PID" >"$PID_FILE"
    echo "Archivox started on PID $LISTENER_PID"
    echo "Open: http://127.0.0.1:$PORT"
    exit 0
  fi

  if ! kill -0 "$LAUNCH_PID" >/dev/null 2>&1 && [[ -z "$LISTENER_PID" ]]; then
    break
  fi

  sleep 1
done

echo "Archivox failed to start" >&2
cat "$ERR_LOG" >&2 || true
exit 1
