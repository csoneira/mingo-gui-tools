# MINGO GUI Tools

Small graphical utilities and desktop launchers used around the MINGO / miniTRASGO workflow.

This repository is primarily a collection of independent tools rather than a single application. Some directories contain a complete Python/Tkinter GUI, while others contain local launchers that open GUI scripts installed on the remote `mingo` host through SSH X11 forwarding.

## Repository contents

| Directory | Purpose | Implementation in this repository |
| --- | --- | --- |
| `GUI_MINGO_ANALYSIS_CONTROL` | Launches the MINGO Step 1 and/or simulation status GUIs. | Launcher only. The Python GUIs are expected on the remote `mingo` host. |
| `GUI_MINGO_CALIBRATION_METADATA` | Launches the calibration metadata/timeline GUI. | Launcher only. The Python GUI is expected on the remote `mingo` host. |
| `GUI_MINGO_CRON_LOGS` | Read-only matrix viewer for selected `DATAFLOW_v3` cron logs, including status, tail preview and live follow. | Python/Tkinter GUI plus launcher and desktop integration. |
| `GUI_MINGO_TABLE_VIEWER` | Legacy/compatibility desktop launcher currently targeting the Step 1 status-timeline GUI under the `MASTER/ANCILLARY/PIPELINE_REAL_TIME_CHECK` tree. | Launcher only; there is no standalone table-viewer Python implementation here. |
| `GUI_NETWORK_CONTROL` | miniTRASGO station status monitor: checks hosts through SSH, the analysis process and DAQ-file recency. | Python/Tkinter GUI plus desktop launcher. |

Each subdirectory is intentionally self-contained and has its own `README.md`. Treat that subdirectory documentation as authoritative for tool-specific behavior.

## Remote-launcher model

Most MINGO launchers use the SSH alias:

```text
mingo
```

and open the remote GUI with X11 forwarding (`ssh -X`). Therefore the local machine normally needs:

- a working `mingo` entry in `~/.ssh/config`;
- key-based SSH access suitable for non-interactive preflight checks;
- X11 forwarding enabled locally and remotely;
- Bash and OpenSSH;
- Python 3 on the remote host;
- the referenced remote GUI script installed at the expected location.

Some launchers additionally use `zenity`, `kdialog` or `notify-send` when available.

### Current default remote targets

`GUI_MINGO_ANALYSIS_CONTROL` launches:

```text
/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/step1_status_timeline_gui.py
/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/simulation_status_timeline_gui.py
```

`GUI_MINGO_CALIBRATION_METADATA` launches:

```text
/home/mingo/DATAFLOW_v3/OPERATIONS/NOTIFICATIONS/STATUS_GUI/task2_calibration_timeline_gui.py
```

`GUI_MINGO_CRON_LOGS` defaults to:

```text
/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/mingo_cron_logs_gui.py
```

The legacy `GUI_MINGO_TABLE_VIEWER` launcher currently defaults to:

```text
/home/mingo/DATAFLOW_v3/MASTER/ANCILLARY/PIPELINE_REAL_TIME_CHECK/step1_status_timeline_gui.py
```

Most of these paths can be overridden through environment variables defined by the corresponding launcher.

## Quick start

Clone the repository:

```bash
git clone https://github.com/csoneira/mingo-gui-tools.git
cd mingo-gui-tools
```

Then enter the desired tool directory. Remote MINGO launchers generally support:

```bash
./launch_mingo_gui.sh
```

and, where provided:

```bash
./install_desktop_launcher.sh
```

The network-control GUI is run directly with Python:

```bash
cd GUI_NETWORK_CONTROL
python3 mingo_status_gui.py
```

See the README inside an individual directory for tool-specific options and deployment details.

## Tool notes

### MINGO analysis control

`GUI_MINGO_ANALYSIS_CONTROL/launch_mingo_gui.sh` can launch the Step 1 GUI, the simulation GUI, or both. It supports explicit command-line selection as well as a graphical chooser when `zenity` or `kdialog` is available.

Useful modes include:

```bash
./launch_mingo_gui.sh --step1
./launch_mingo_gui.sh --simulation
./launch_mingo_gui.sh --both
./launch_mingo_gui.sh --step1 --foreground --debug
```

### Calibration metadata

`GUI_MINGO_CALIBRATION_METADATA` is a local launcher/desktop integration layer for the remote calibration metadata GUI. Its subdirectory README documents environment overrides and installation paths.

### Cron logs

`GUI_MINGO_CRON_LOGS` contains the GUI implementation itself (`mingo_cron_logs_gui.py`). The application is designed to inspect selected cron logs without modifying them. It supports a configurable station/task matrix, status classification, tail previews and multiple live-follow tabs.

The intended deployment model is to copy the Python GUI to the MINGO host and start it through the local SSH/X11 launcher.

### Table viewer compatibility launcher

`GUI_MINGO_TABLE_VIEWER` is retained for compatibility with the older `MASTER/ANCILLARY/PIPELINE_REAL_TIME_CHECK` remote path. Its current launcher does not provide an independent table-viewer implementation, and its historical `--simulation`/`--both` options resolve to the Step 1 target unless `SIMULATION_REMOTE_SCRIPT` is explicitly overridden.

For current Step 1/simulation status launching, `GUI_MINGO_ANALYSIS_CONTROL` is the clearer entry point.

### Network control

`GUI_NETWORK_CONTROL/mingo_status_gui.py` is a local Tkinter status monitor for `mingo0X` hosts. It uses SSH to check connectivity, process state and the age of the latest DAQ file. See `GUI_NETWORK_CONTROL/README.md` for CLI parameters and status semantics.

## Scope

This repository contains operational convenience GUIs and launchers tied to the MINGO/miniTRASGO environment. Several tools depend on external scripts, directory layouts and SSH aliases that are not reproduced here, so cloning this repository alone is not sufficient to recreate the complete MINGO software environment.
