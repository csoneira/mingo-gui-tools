# Mingo Calibration Metadata GUI Launcher

Launches the remote GUI script over SSH X11 forwarding:

`/home/mingo/DATAFLOW_v3/OPERATIONS/NOTIFICATIONS/STATUS_GUI/task2_calibration_timeline_gui.py`

## Install desktop app

```bash
./install_desktop_launcher.sh
```

This installs:

- `~/.local/share/applications/mingo-calibration-metadata.desktop`
- optional desktop copy: `~/Desktop/mingo-calibration-metadata.desktop`
- icon target: `~/.local/share/icons/hicolor/256x256/apps/mingo-calibration-metadata.png`

## Run manually

```bash
./launch_mingo_gui.sh
```

Foreground mode (helpful for debugging):

```bash
./launch_mingo_gui.sh --foreground
```

## Optional environment overrides

- `REMOTE_HOST` (default: `mingo`)
- `REMOTE_SCRIPT` (default: calibration metadata script path)
- `MINGO_GUI_LOG_DIR` (default: `/tmp/mingo-calibration-metadata-gui`)

## Add icon later

When ready, put your icon file here:

`logo_mingo_calibration.png` (preferred) or `logo_mingo_calibration_metadata.png`

Then rerun:

```bash
./install_desktop_launcher.sh
```
