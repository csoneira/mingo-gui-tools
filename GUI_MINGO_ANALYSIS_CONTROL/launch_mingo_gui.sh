#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-mingo}"
STEP1_REMOTE_SCRIPT="${STEP1_REMOTE_SCRIPT:-${REMOTE_SCRIPT:-/home/mingo/DATAFLOW_v3/OPERATIONS/NOTIFICATIONS/STATUS_GUI/step1_status_timeline_gui.py}}"
SIMULATION_REMOTE_SCRIPT="${SIMULATION_REMOTE_SCRIPT:-/home/mingo/DATAFLOW_v3/OPERATIONS/NOTIFICATIONS/STATUS_GUI/simulation_status_timeline_gui.py}"
LOG_DIR="${MINGO_GUI_LOG_DIR:-/tmp/mingo-gui}"
LOG_FILE="$LOG_DIR/launcher.log"
SSH_OPTS=(-X -o ExitOnForwardFailure=yes -o ClearAllForwardings=yes)
SSH_VERBOSE_OPTS=()
FOREGROUND=0
DEBUG=0
MODE="ask"

print_usage() {
  cat <<'EOF'
Usage: launch_mingo_gui.sh [options]

Options:
  --step1        Launch Step 1 GUI
  --simulation   Launch Simulation GUI
  --both         Launch both GUIs
  --ask          Show chooser dialog (default)
  --foreground   Keep process attached (single GUI only)
  --debug        Enable verbose SSH logging
  --help         Show this help
EOF
}

prompt_mode() {
  if command -v zenity >/dev/null 2>&1; then
    local choice
    choice="$(zenity --list --radiolist \
      --title="Select Mingo GUI" \
      --text="Choose what to launch:" \
      --column="" --column="Option" \
      TRUE "Step 1" \
      FALSE "Simulation" \
      FALSE "Both" \
      --height=360 --width=520 2>/dev/null || true)"
    case "$choice" in
      "Step 1")
        MODE="step1"
        ;;
      "Simulation")
        MODE="simulation"
        ;;
      "Both")
        MODE="both"
        ;;
      *)
        echo "No selection made."
        exit 1
        ;;
    esac
    return
  fi

  if command -v kdialog >/dev/null 2>&1; then
    local selection
    selection="$(kdialog --geometry 520x360 --menu "Choose what to launch" step1 "Step 1" simulation "Simulation" both "Both" 2>/dev/null || true)"
    case "$selection" in
      step1|simulation|both)
        MODE="$selection"
        ;;
      *)
        echo "No selection made."
        exit 1
        ;;
    esac
    return
  fi

  echo "Error: no GUI dialog tool found (install zenity or kdialog), or pass --step1/--simulation/--both."
  exit 1
}

build_remote_command() {
  local remote_script="$1"
  if [[ $DEBUG -eq 1 ]]; then
    printf 'PYTHONUNBUFFERED=1 python3 -u "%s"' "$remote_script"
  else
    printf 'python3 "%s"' "$remote_script"
  fi
}

ssh_preflight() {
  if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$REMOTE_HOST" "command -v python3 >/dev/null" \
    >>"$LOG_FILE" 2>&1; then
    local failure_reason
    failure_reason="$(tail -n 2 "$LOG_FILE" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g')"
    notify_failure "${failure_reason:-SSH preflight failed. See $LOG_FILE}"
    exit 1
  fi
}

launch_detached() {
  local remote_script="$1"
  local remote_command
  remote_command="$(build_remote_command "$remote_script")"
  nohup ssh "${SSH_OPTS[@]}" "${SSH_VERBOSE_OPTS[@]}" "$REMOTE_HOST" "$remote_command" \
    >>"$LOG_FILE" 2>&1 < /dev/null &
}

launch_foreground() {
  local remote_script="$1"
  local remote_command
  remote_command="$(build_remote_command "$remote_script")"
  ssh "${SSH_OPTS[@]}" "${SSH_VERBOSE_OPTS[@]}" "$REMOTE_HOST" "$remote_command" 2>&1 | tee -a "$LOG_FILE"
  exit "${PIPESTATUS[0]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --step1)
      MODE="step1"
      ;;
    --simulation)
      MODE="simulation"
      ;;
    --both)
      MODE="both"
      ;;
    --ask)
      MODE="ask"
      ;;
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
      break
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

notify_failure() {
  local message="$1"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Mingo GUI launch failed" "$message" >/dev/null 2>&1 || true
  fi
}

{
  echo "[$(date -Is)] Launch requested"
  echo "[$(date -Is)] Host: $REMOTE_HOST"
  echo "[$(date -Is)] Step 1 script: $STEP1_REMOTE_SCRIPT"
  echo "[$(date -Is)] Simulation script: $SIMULATION_REMOTE_SCRIPT"
  echo "[$(date -Is)] Foreground: $FOREGROUND Debug: $DEBUG"
} >> "$LOG_FILE"

if [[ "$MODE" == "ask" ]]; then
  prompt_mode
fi

declare -a SELECTED_SCRIPTS=()
case "$MODE" in
  step1)
    SELECTED_SCRIPTS+=("$STEP1_REMOTE_SCRIPT")
    ;;
  simulation)
    SELECTED_SCRIPTS+=("$SIMULATION_REMOTE_SCRIPT")
    ;;
  both)
    SELECTED_SCRIPTS+=("$STEP1_REMOTE_SCRIPT" "$SIMULATION_REMOTE_SCRIPT")
    ;;
  *)
    echo "Error: unknown mode '$MODE'."
    exit 1
    ;;
esac

echo "[$(date -Is)] Mode: $MODE" >> "$LOG_FILE"

ssh_preflight

if [[ $FOREGROUND -eq 1 && ${#SELECTED_SCRIPTS[@]} -ne 1 ]]; then
  echo "Error: --foreground supports only one GUI. Use --step1 or --simulation." | tee -a "$LOG_FILE"
  exit 1
fi

if [[ $FOREGROUND -eq 1 ]]; then
  launch_foreground "${SELECTED_SCRIPTS[0]}"
fi

for script in "${SELECTED_SCRIPTS[@]}"; do
  echo "[$(date -Is)] Launching (detached): $script" >> "$LOG_FILE"
  launch_detached "$script"
done
