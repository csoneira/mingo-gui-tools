#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-mingo}"
REMOTE_SCRIPT="${REMOTE_SCRIPT:-/home/mingo/DATAFLOW_v3/OPERATIONS/NOTIFICATIONS/STATUS_GUI/task2_calibration_timeline_gui.py}"
LOG_DIR="${MINGO_GUI_LOG_DIR:-/tmp/mingo-calibration-metadata-gui}"
LOG_FILE="$LOG_DIR/launcher.log"
SSH_OPTS=(-X -o ExitOnForwardFailure=yes -o ClearAllForwardings=yes)
SSH_VERBOSE_OPTS=()
FOREGROUND=0
DEBUG=0

print_usage() {
  cat <<'EOF'
Usage: launch_mingo_gui.sh [options]

Options:
  --foreground   Keep process attached
  --debug        Enable verbose SSH logging
  --help         Show this help
EOF
}

build_remote_command() {
  if [[ $DEBUG -eq 1 ]]; then
    printf 'PYTHONUNBUFFERED=1 python3 -u "%s"' "$REMOTE_SCRIPT"
  else
    printf 'python3 "%s"' "$REMOTE_SCRIPT"
  fi
}

notify_failure() {
  local message="$1"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Mingo GUI launch failed" "$message" >/dev/null 2>&1 || true
  fi
}

ssh_preflight() {
  local remote_script_quoted
  printf -v remote_script_quoted '%q' "$REMOTE_SCRIPT"

  if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$REMOTE_HOST" \
    "command -v python3 >/dev/null && test -f $remote_script_quoted" \
    >>"$LOG_FILE" 2>&1; then
    local failure_reason
    failure_reason="$(tail -n 2 "$LOG_FILE" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g')"
    notify_failure "${failure_reason:-SSH preflight failed. See $LOG_FILE}"
    exit 1
  fi
}

launch_detached() {
  local remote_command
  remote_command="$(build_remote_command)"
  nohup ssh "${SSH_OPTS[@]}" "${SSH_VERBOSE_OPTS[@]}" "$REMOTE_HOST" "$remote_command" \
    >>"$LOG_FILE" 2>&1 < /dev/null &
}

launch_foreground() {
  local remote_command
  remote_command="$(build_remote_command)"
  ssh "${SSH_OPTS[@]}" "${SSH_VERBOSE_OPTS[@]}" "$REMOTE_HOST" "$remote_command" 2>&1 | tee -a "$LOG_FILE"
  exit "${PIPESTATUS[0]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --foreground)
      FOREGROUND=1
      ;;
    --debug)
      DEBUG=1
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Error: unknown option '$1'."
      print_usage
      exit 1
      ;;
  esac
  shift
done

if [[ $DEBUG -eq 1 ]]; then
  set -x
  SSH_VERBOSE_OPTS=(-vvv -o LogLevel=VERBOSE)
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "Error: ssh is not installed."
  exit 1
fi

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"

{
  echo "[$(date -Is)] Launch requested"
  echo "[$(date -Is)] Host: $REMOTE_HOST"
  echo "[$(date -Is)] Script: $REMOTE_SCRIPT"
  echo "[$(date -Is)] Foreground: $FOREGROUND Debug: $DEBUG"
} >> "$LOG_FILE"

ssh_preflight

if [[ $FOREGROUND -eq 1 ]]; then
  echo "[$(date -Is)] Launching (foreground): $REMOTE_SCRIPT" >> "$LOG_FILE"
  launch_foreground
fi

echo "[$(date -Is)] Launching (detached): $REMOTE_SCRIPT" >> "$LOG_FILE"
launch_detached
