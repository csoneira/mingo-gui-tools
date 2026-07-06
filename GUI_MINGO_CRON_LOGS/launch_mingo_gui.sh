#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-mingo}"
REMOTE_SCRIPT="${REMOTE_SCRIPT:-/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/mingo_cron_logs_gui.py}"
REMOTE_DATAFLOW_ROOT="${DATAFLOW_ROOT:-/home/mingo/DATAFLOW_v3}"
REMOTE_CRON_LOG_ROOT="${CRON_LOG_ROOT:-/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/CRON_LOGS}"
REMOTE_CONFIG="${MINGO_CRON_LOGS_CONFIG:-/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/GUI_CONFIGS/mingo_cron_log_matrix_layout.json}"
LOG_DIR="${MINGO_GUI_LOG_DIR:-/tmp/mingo-cron-logs-gui}"
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

Environment:
  REMOTE_HOST             SSH host alias (default: mingo)
  REMOTE_SCRIPT           Remote Python GUI path
  DATAFLOW_ROOT           Remote DATAFLOW root
  CRON_LOG_ROOT           Remote cron log root
  MINGO_CRON_LOGS_CONFIG  Remote GUI layout JSON
  MINGO_GUI_LOG_DIR       Local launcher log directory
EOF
}

notify_failure() {
  local message="$1"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Mingo Cron Logs launch failed" "$message" >/dev/null 2>&1 || true
  fi
}

quote_arg() {
  printf '%q' "$1"
}

build_remote_command() {
  local script dataflow cronroot config
  script="$(quote_arg "$REMOTE_SCRIPT")"
  dataflow="$(quote_arg "$REMOTE_DATAFLOW_ROOT")"
  cronroot="$(quote_arg "$REMOTE_CRON_LOG_ROOT")"
  config="$(quote_arg "$REMOTE_CONFIG")"
  if [[ $DEBUG -eq 1 ]]; then
    printf 'PYTHONUNBUFFERED=1 python3 -u %s --dataflow-root %s --cron-log-root %s --config %s' "$script" "$dataflow" "$cronroot" "$config"
  else
    printf 'python3 %s --dataflow-root %s --cron-log-root %s --config %s' "$script" "$dataflow" "$cronroot" "$config"
  fi
}

ssh_preflight() {
  local remote_script_quoted
  remote_script_quoted="$(quote_arg "$REMOTE_SCRIPT")"
  if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$REMOTE_HOST" \
    "if ! command -v python3 >/dev/null 2>&1; then echo 'python3 not found on remote host'; exit 10; fi; if ! test -f $remote_script_quoted; then echo 'remote script not found: $remote_script_quoted'; exit 11; fi" \
    >>"$LOG_FILE" 2>&1; then
    local failure_reason
    failure_reason="$(tail -n 8 "$LOG_FILE" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g')"
    echo "Error: SSH preflight failed. Check host '$REMOTE_HOST', X11 forwarding, python3, and remote script: $REMOTE_SCRIPT" | tee -a "$LOG_FILE"
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
  echo "[$(date -Is)] DATAFLOW root: $REMOTE_DATAFLOW_ROOT"
  echo "[$(date -Is)] Cron log root: $REMOTE_CRON_LOG_ROOT"
  echo "[$(date -Is)] Config: $REMOTE_CONFIG"
  echo "[$(date -Is)] Foreground: $FOREGROUND Debug: $DEBUG"
} >> "$LOG_FILE"

ssh_preflight

if [[ $FOREGROUND -eq 1 ]]; then
  echo "[$(date -Is)] Launching (foreground): $REMOTE_SCRIPT" >> "$LOG_FILE"
  launch_foreground
fi

echo "[$(date -Is)] Launching (detached): $REMOTE_SCRIPT" >> "$LOG_FILE"
launch_detached
