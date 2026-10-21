# MINGO Table Viewer Launcher

This directory is retained as a **legacy/compatibility launcher**.

Despite the directory and desktop-entry name, it does not currently contain a standalone table-viewer Python application. The launcher opens a remote Step 1 status/timeline GUI over SSH X11 forwarding.

## Current default target

```text
/home/mingo/DATAFLOW_v3/MASTER/ANCILLARY/PIPELINE_REAL_TIME_CHECK/step1_status_timeline_gui.py
```

`REMOTE_HOST` defaults to `mingo`.

The launcher accepts `STEP1_REMOTE_SCRIPT` or the compatibility variable `REMOTE_SCRIPT` to override the target.

## Run manually

```bash
./launch_mingo_gui.sh
```

The default mode is Step 1. The launcher still exposes historical `--simulation` and `--both` options, but unless `SIMULATION_REMOTE_SCRIPT` is explicitly set, the simulation target resolves to the same Step 1 script. For that reason these options should not be interpreted as proof that two separate remote GUIs are configured here.

For troubleshooting:

```bash
./launch_mingo_gui.sh --foreground --debug
```

## Desktop launcher

Install with:

```bash
./install_desktop_launcher.sh
```

The installer uses `mingo-gui.desktop.in` and `logo_mingo_tables.png` and creates the local application entry `mingo-table-viewer.desktop`.

## Relationship to `GUI_MINGO_ANALYSIS_CONTROL`

`GUI_MINGO_ANALYSIS_CONTROL` is the clearer current launcher for the Step 1 and simulation status GUIs under the `OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI` tree.

This directory points instead to the older `MASTER/ANCILLARY/PIPELINE_REAL_TIME_CHECK` location. It is therefore kept for compatibility rather than being treated as the canonical analysis-control launcher.

Do not remove it solely on the basis of its name if an existing desktop installation or workflow still depends on this older remote path.
