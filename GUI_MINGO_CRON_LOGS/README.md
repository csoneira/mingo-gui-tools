# MINGO Cron Log Matrix Viewer

Tkinter GUI for inspecting selected cron logs from `DATAFLOW_v3` as a fixed control-room matrix.

Rows are logical scripts or pipeline tasks. Columns are selected stations: `Global`, `0`, `1`, `2`, `3`, and `4`. The GUI is not a recursive log browser and does not show every cron log by default. It only shows the stations and scripts selected in the loaded layout config.

The GUI is read-only with respect to cron logs. It uses `os.stat`, efficient tail reads, and `tail -n N -F` for live follow tabs. It never modifies, truncates, rotates, deletes, or creates cron log files. The only writable file is its own layout/config JSON.

## Remote Execution Model

This project follows the existing MINGO launcher convention: the local launcher opens a remote Python GUI over SSH X11 forwarding on host alias `mingo`.

Default remote script path:

```bash
/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_SCRIPTS/NOTIFICATIONS/STATUS_GUI/mingo_cron_logs_gui.py
```

Copy `mingo_cron_logs_gui.py` to that path on `mingo`, or set `REMOTE_SCRIPT` to wherever you deploy it remotely. The Python script is expected to run on `mingo` and read `/home/mingo/DATAFLOW_v3` directly. It does not use local copies of logs.

## Defaults

- `REMOTE_HOST=mingo`
- `DATAFLOW_ROOT=/home/mingo/DATAFLOW_v3`
- `CRON_LOG_ROOT=/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/CRON_LOGS`
- Config path: `/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/GUI_CONFIGS/mingo_cron_log_matrix_layout.json`
- Fallback config path: `~/.config/mingo_cron_logs/layout.json`
- Launcher log: `/tmp/mingo-cron-logs-gui/launcher.log`

## Layout Config

The default layout is stored as pretty-printed, human-editable JSON. It contains selected stations, selected scripts, tail length, refresh interval, auto-refresh, auto-scroll, inactive-entry display, and status age thresholds.

Use the GUI controls to choose station columns and script rows. Then press:

```text
Set current layout as default
```

That button saves the currently visible station columns, visible script rows, tail-line count, refresh interval, auto-scroll, auto-refresh, and inactive-entry setting to the JSON config file. It never writes to cron logs.

The Settings menu includes:

- Load default layout
- Reset to built-in layout
- Set current layout as default
- Open config file path
- Reload config from disk

`Open config file path` opens an in-GUI JSON editor so the layout can be modified from inside the application. You can also edit the JSON manually with any text editor and then use `Reload config from disk`.

## Matrix Status

Each applicable cell shows a compact status:

- `OK`: file exists, is non-empty, is fresh for its frequency hint, and the inspected tail has no suspicious pattern
- `OLD`: file exists but is older than the configured threshold
- `EMPTY`: file exists but has zero bytes
- `MISSING`: declared manifest path does not exist
- `ERROR`: suspicious pattern, unreadable file, or read failure
- `N/A`: the row does not apply to that station

Suspicious patterns include `Traceback`, `ERROR`, `CRITICAL`, `Exception`, `FAILED`, `WARNING`, `lock busy`, `resource gate`, `no such file`, `permission denied`, `killed`, `out of memory`, `stale lock`, and `rsync error`.

Double-click an applicable cell to load its last lines in the preview. Right-click a cell for `Open last lines`, `Follow live`, `Copy path`, and `Refresh this cell`. Multiple live tails can run simultaneously; each uses its own notebook tab and a background thread.

## Run Manually

```bash
./launch_mingo_gui.sh
```

Foreground mode:

```bash
./launch_mingo_gui.sh --foreground
```

Verbose SSH debug:

```bash
./launch_mingo_gui.sh --foreground --debug
```

The launcher performs a BatchMode SSH preflight, checks `python3`, checks that `REMOTE_SCRIPT` exists remotely, and writes failures to `/tmp/mingo-cron-logs-gui/launcher.log`. If available, it also uses `notify-send` on failure.

## Environment Overrides

- `REMOTE_HOST`
- `REMOTE_SCRIPT`
- `DATAFLOW_ROOT`
- `CRON_LOG_ROOT`
- `MINGO_CRON_LOGS_CONFIG`
- `MINGO_GUI_LOG_DIR`

Example:

```bash
REMOTE_SCRIPT=/home/mingo/mingo_cron_logs_gui.py ./launch_mingo_gui.sh --foreground
```

## Python CLI

When already on `mingo`, the GUI script can be run directly:

```bash
python3 mingo_cron_logs_gui.py
```

Options:

```bash
python3 mingo_cron_logs_gui.py \
  --dataflow-root /home/mingo/DATAFLOW_v3 \
  --cron-log-root /home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/CRON_LOGS \
  --config /home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/GUI_CONFIGS/mingo_cron_log_matrix_layout.json \
  --lines 200 \
  --refresh-interval 30
```

Additional flags:

- `--include-inactive`
- `--no-auto-refresh`
- `--reset-layout`

## Install Desktop Launcher

```bash
./install_desktop_launcher.sh
```

This installs `~/.local/share/applications/mingo-cron-logs.desktop` and optionally copies it to `~/Desktop`. An optional icon can be added later as `logo_mingo_cron_logs.png` or `logo_mingo.png`, then rerun the installer.

## Debug SSH/X11

Check the local log first:

```bash
cat /tmp/mingo-cron-logs-gui/launcher.log
```

Common causes:

- Host alias `mingo` is missing from SSH config
- SSH key auth is not available for BatchMode
- X11 forwarding is disabled locally or remotely
- `python3` is missing on `mingo`
- `REMOTE_SCRIPT` was not copied to the remote path

Run `./launch_mingo_gui.sh --foreground --debug` to keep the SSH session attached and log verbose SSH output.
