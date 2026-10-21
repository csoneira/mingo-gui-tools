# MINGO Analysis Control Launcher

Local desktop/SSH launcher for the MINGO analysis status GUIs.

This directory does **not** contain the Python GUI implementations themselves. It opens the corresponding scripts on the remote `mingo` host through SSH X11 forwarding.

## Remote GUIs

The launcher currently targets:

```text
/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/step1_status_timeline_gui.py
/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/simulation_status_timeline_gui.py
```

The paths can be overridden with `STEP1_REMOTE_SCRIPT` and `SIMULATION_REMOTE_SCRIPT`. `REMOTE_HOST` defaults to `mingo`.

## Run manually

```bash
./launch_mingo_gui.sh
```

With no explicit mode, the launcher presents a chooser when `zenity` or `kdialog` is available.

Explicit modes:

```bash
./launch_mingo_gui.sh --step1
./launch_mingo_gui.sh --simulation
./launch_mingo_gui.sh --both
```

For troubleshooting a single GUI:

```bash
./launch_mingo_gui.sh --step1 --foreground --debug
```

`--foreground` is intentionally restricted to a single selected GUI.

## Desktop launcher

Install the local application entry with:

```bash
./install_desktop_launcher.sh
```

The installer uses `mingo-gui.desktop.in` and `logo_mingo_analysis.png`.

## Requirements

- Bash and OpenSSH on the local machine
- a working SSH alias `mingo` (or `REMOTE_HOST` override)
- X11 forwarding available locally and remotely
- Python 3 on the remote host
- the remote GUI scripts installed at the configured paths

Launcher diagnostics are written under `/tmp/mingo-gui` by default. Override the directory with `MINGO_GUI_LOG_DIR`.
