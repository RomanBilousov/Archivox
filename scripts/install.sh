#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${ARCHIVOX_REPO_URL:-https://github.com/RomanBilousov/Archivox.git}"
REPO_BRANCH="${ARCHIVOX_REPO_BRANCH:-main}"
START_MODE="${ARCHIVOX_START_MODE:-background}"
INSTALL_LAUNCH_AGENT="${ARCHIVOX_INSTALL_LAUNCH_AGENT:-0}"
INSTALL_LAUNCHER_APP="${ARCHIVOX_INSTALL_LAUNCHER_APP:-0}"
OPEN_BROWSER="${ARCHIVOX_OPEN_BROWSER:-1}"
PORT="${ARCHIVOX_PORT:-8420}"
OS_NAME="$(uname -s)"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"

log() {
  printf '[Archivox] %s\n' "$*"
}

fail() {
  printf '[Archivox] %s\n' "$*" >&2
  exit 1
}

ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
  fi
}

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

install_uv() {
  log "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
}

detect_default_install_dir() {
  if [[ "$OS_NAME" == "Darwin" ]]; then
    printf '%s\n' "$HOME/Library/Application Support/Archivox/repo"
  else
    printf '%s\n' "$HOME/.local/share/archivox/repo"
  fi
}

detect_local_repo_root() {
  if [[ -n "$SCRIPT_SOURCE" && -f "$SCRIPT_SOURCE" ]]; then
    local script_dir repo_root
    script_dir="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    repo_root="$(cd "$script_dir/.." && pwd)"
    if [[ -d "$repo_root/.git" ]]; then
      printf '%s\n' "$repo_root"
      return 0
    fi
  fi
  return 1
}

clone_or_update_repo() {
  local install_dir="$1"
  if [[ -n "${LOCAL_REPO_ROOT:-}" && "$install_dir" == "$LOCAL_REPO_ROOT" ]]; then
    log "Using the current local checkout at $install_dir"
    return 0
  fi

  if [[ -d "$install_dir/.git" ]]; then
    log "Updating existing repo in $install_dir"
    git -C "$install_dir" fetch origin "$REPO_BRANCH"
    git -C "$install_dir" checkout "$REPO_BRANCH"
    git -C "$install_dir" pull --ff-only origin "$REPO_BRANCH"
    return 0
  fi

  if [[ -e "$install_dir" && ! -d "$install_dir/.git" ]]; then
    fail "Install directory already exists but is not a git repository: $install_dir"
  fi

  mkdir -p "$(dirname "$install_dir")"
  log "Cloning repo into $install_dir"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$install_dir"
}

open_url() {
  local url="$1"
  if [[ "$OPEN_BROWSER" != "1" ]]; then
    return 0
  fi

  if [[ "$OS_NAME" == "Darwin" ]]; then
    open "$url" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
}

LOCAL_REPO_ROOT="$(detect_local_repo_root || true)"
DEFAULT_INSTALL_DIR="$(detect_default_install_dir)"
INSTALL_DIR="${ARCHIVOX_INSTALL_DIR:-${LOCAL_REPO_ROOT:-$DEFAULT_INSTALL_DIR}}"

ensure_command git
ensure_command curl
ensure_command python3

if ! UV_BIN="$(find_uv_bin)"; then
  install_uv
  UV_BIN="$(find_uv_bin)" || fail "uv installation finished but uv binary still was not found."
fi

clone_or_update_repo "$INSTALL_DIR"
cd "$INSTALL_DIR"

log "Syncing Python dependencies"
"$UV_BIN" sync
chmod +x scripts/*.sh

if [[ "$INSTALL_LAUNCH_AGENT" == "1" ]]; then
  if [[ "$OS_NAME" != "Darwin" ]]; then
    fail "LaunchAgent install is only supported on macOS."
  fi
  log "Installing LaunchAgent"
  UV_BIN="$UV_BIN" ./scripts/install_launch_agent.sh
fi

if [[ "$INSTALL_LAUNCHER_APP" == "1" ]]; then
  if [[ "$OS_NAME" != "Darwin" ]]; then
    fail "Launcher app install is only supported on macOS."
  fi
  log "Installing launcher app"
  UV_BIN="$UV_BIN" ./scripts/install_launcher_app.sh
fi

URL="http://127.0.0.1:$PORT"

case "$START_MODE" in
  background)
    log "Starting Archivox in the background"
    UV_BIN="$UV_BIN" ARCHIVOX_PORT="$PORT" ./scripts/start_background.sh
    open_url "$URL"
    ;;
  foreground)
    log "Starting Archivox in the foreground"
    open_url "$URL"
    exec "$UV_BIN" run archivox
    ;;
  none)
    log "Install completed without starting the app"
    ;;
  *)
    fail "Unknown ARCHIVOX_START_MODE: $START_MODE (expected background, foreground, or none)"
    ;;
esac

log "Repo: $INSTALL_DIR"
log "Open: $URL"
log "Status: $INSTALL_DIR/scripts/status_background.sh"
