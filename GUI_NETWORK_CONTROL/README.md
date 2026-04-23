# miniTRASGO Status Monitor

Small Tkinter GUI to monitor mingo0X hosts via SSH, check the analysis process,
and show the age of the latest DAQ file.

## Usage
```bash
python3 mingo_status_gui.py [--hosts HOSTS] [--process PROCESS] [--interval SECONDS]
```

- If you create the desktop launcher and later move the repo, re-run
  `create_desktop_launcher.sh`. You can also set `MINITRASGO_REPO_DIR` to
  point at the repo path when running the launcher script.

- `--hosts`: comma-separated SSH aliases (default: auto-detect mingo0X from `~/.ssh/config`)
- `--process`: process match for `pgrep -f` (default: `dabc_exe`)
- `--interval`: seconds between checks (min 2)

## Status colors
- Red: not connected (SSH failed)
- Orange: connected, process not running
- Purple: connected, process running but no recent file
- Green: connected, process running and recent file

## File recency
- Latest file is chosen from `mi<station>*.dat*` under
  `/home/rpcuser/gate/system/devices/TRB3/data/daqData/asci`.
- "Recent" means the latest file age is <= 3h (see `STALE_FILE_THRESHOLD_S` in
  `mingo_status_gui.py`).

## Notes
- Station id is derived from the host name (`mingo0X` -> station `0X`).
- Auto-restart attempts to kill matching autossh/ssh tunnel processes once per minute.
