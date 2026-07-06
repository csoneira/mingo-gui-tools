#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/mingo-gui.desktop.in"
LAUNCHER_FILE="$SCRIPT_DIR/launch_mingo_gui.sh"
LOGO_CANDIDATES=(
  "$SCRIPT_DIR/logo_mingo_cron_logs.png"
  "$SCRIPT_DIR/logo_mingo.png"
)
APPS_DIR="$HOME/.local/share/applications"
APP_FILE="$APPS_DIR/mingo-cron-logs.desktop"
LEGACY_APP_FILE="$APPS_DIR/mingo-gui.desktop"
DESKTOP_DIR="$HOME/Desktop"
ICON_NAME="mingo-cron-logs"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/$ICON_NAME.png"
ICON_VALUE="$ICON_NAME"
LOGO_FILE=""

if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "Error: template not found: $TEMPLATE_FILE"
  exit 1
fi

if [[ ! -f "$LAUNCHER_FILE" ]]; then
  echo "Error: launcher not found: $LAUNCHER_FILE"
  exit 1
fi

mkdir -p "$APPS_DIR"
mkdir -p "$ICON_DIR"

for candidate in "${LOGO_CANDIDATES[@]}"; do
  if [[ -f "$candidate" ]]; then
    LOGO_FILE="$candidate"
    break
  fi
done

if [[ -n "$LOGO_FILE" ]]; then
  cp "$LOGO_FILE" "$ICON_FILE"
  ICON_VALUE="$ICON_FILE"
  echo "Using logo: $LOGO_FILE"
  echo "Installed icon: $ICON_FILE"
else
  echo "Warning: optional icon not found. Checked:"
  for candidate in "${LOGO_CANDIDATES[@]}"; do
    echo "  - $candidate"
  done
  echo "The app will be installed with the desktop theme fallback icon."
fi

if [[ -f "$LEGACY_APP_FILE" ]] && grep -Fq "Exec=$LAUNCHER_FILE" "$LEGACY_APP_FILE"; then
  rm -f "$LEGACY_APP_FILE"
fi

ESCAPED_LAUNCHER="${LAUNCHER_FILE//|/\\|}"
ESCAPED_ICON_VALUE="${ICON_VALUE//|/\\|}"
sed \
  -e "s|__LAUNCHER_PATH__|$ESCAPED_LAUNCHER|g" \
  -e "s|__ICON_NAME__|$ESCAPED_ICON_VALUE|g" \
  "$TEMPLATE_FILE" > "$APP_FILE"

chmod +x "$LAUNCHER_FILE"
chmod +x "$APP_FILE"

if [[ -d "$DESKTOP_DIR" ]]; then
  cp "$APP_FILE" "$DESKTOP_DIR/mingo-cron-logs.desktop"
  chmod +x "$DESKTOP_DIR/mingo-cron-logs.desktop"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -q "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Installed launcher: $APP_FILE"
if [[ -d "$DESKTOP_DIR" ]]; then
  echo "Copied launcher to desktop: $DESKTOP_DIR/mingo-cron-logs.desktop"
fi
