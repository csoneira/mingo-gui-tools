#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/mingo-gui.desktop.in"
LAUNCHER_FILE="$SCRIPT_DIR/launch_mingo_gui.sh"
LOGO_FILE="$SCRIPT_DIR/logo_mingo_calibration_metadata.png"
APPS_DIR="$HOME/.local/share/applications"
APP_FILE="$APPS_DIR/mingo-calibration-metadata.desktop"
LEGACY_APP_FILE="$APPS_DIR/mingo-gui.desktop"
DESKTOP_DIR="$HOME/Desktop"
ICON_NAME="mingo-calibration-metadata"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/$ICON_NAME.png"

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

if [[ -f "$LOGO_FILE" ]]; then
  cp "$LOGO_FILE" "$ICON_FILE"
  echo "Installed icon: $ICON_FILE"
else
  echo "Warning: logo not found: $LOGO_FILE"
  echo "The app will be installed without a custom icon for now."
fi

# Remove old generic launcher only if it points to this app's launcher script.
if [[ -f "$LEGACY_APP_FILE" ]] && grep -Fq "Exec=$LAUNCHER_FILE" "$LEGACY_APP_FILE"; then
  rm -f "$LEGACY_APP_FILE"
fi

ESCAPED_LAUNCHER="${LAUNCHER_FILE//|/\\|}"
sed \
  -e "s|__LAUNCHER_PATH__|$ESCAPED_LAUNCHER|g" \
  -e "s|__ICON_NAME__|$ICON_NAME|g" \
  "$TEMPLATE_FILE" > "$APP_FILE"

chmod +x "$LAUNCHER_FILE"
chmod +x "$APP_FILE"

if [[ -d "$DESKTOP_DIR" ]]; then
  cp "$APP_FILE" "$DESKTOP_DIR/mingo-calibration-metadata.desktop"
  chmod +x "$DESKTOP_DIR/mingo-calibration-metadata.desktop"
fi

echo "Installed launcher: $APP_FILE"
if [[ -d "$DESKTOP_DIR" ]]; then
  echo "Copied launcher to desktop: $DESKTOP_DIR/mingo-calibration-metadata.desktop"
fi
