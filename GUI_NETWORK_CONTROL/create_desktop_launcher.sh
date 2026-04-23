#!/usr/bin/env bash
set -euo pipefail

APP_NAME="miniTRASGO Status"

resolve_repo_dir() {
  local source="${BASH_SOURCE[0]}"
  while [ -h "$source" ]; do
    local dir
    dir="$(cd -P -- "$(dirname -- "$source")" && pwd -P)"
    source="$(readlink "$source")"
    [[ "$source" != /* ]] && source="${dir}/${source}"
  done
  cd -P -- "$(dirname -- "$source")" && pwd -P
}

REPO_DIR="${MINITRASGO_REPO_DIR:-$(resolve_repo_dir)}"
SCRIPT_PATH="${REPO_DIR}/mingo_status_gui.py"
ICON_PATH="${REPO_DIR}/logo_mingo_stations.png"
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/miniTRASGO-status.desktop"

if [[ ! -f "${SCRIPT_PATH}" ]]; then
  echo "error: ${SCRIPT_PATH} not found. Set MINITRASGO_REPO_DIR to the repo path." >&2
  exit 1
fi
if [[ ! -f "${ICON_PATH}" ]]; then
  echo "warning: ${ICON_PATH} not found. Icon may not display." >&2
fi

mkdir -p "${DESKTOP_DIR}"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Name=${APP_NAME}
Exec=/usr/bin/env python3 ${SCRIPT_PATH}
Icon=${ICON_PATH}
Terminal=false
Type=Application
Categories=Utility;
EOF

chmod +x "${BASH_SOURCE[0]}"
chmod +x "${DESKTOP_FILE}"

if command -v gio >/dev/null 2>&1; then
  gio set "${DESKTOP_FILE}" metadata::trusted true >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${DESKTOP_DIR}"
fi

echo "Created launcher: ${DESKTOP_FILE}"
