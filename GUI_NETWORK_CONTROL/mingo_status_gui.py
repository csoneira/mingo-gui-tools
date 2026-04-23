#!/usr/bin/env python3
import os
import re
import subprocess
import threading
import time
import argparse
import tkinter as tk
from tkinter import messagebox, ttk


CONFIG_PATH = os.path.expanduser("~/.ssh/config")
DEFAULT_PROCESS = "dabc_exe"
DEFAULT_INTERVAL_S = 5
FULL_VIEW_SIZE = (555, 420)
COMPACT_VIEW_SIZE = (240, 200)
DAQ_DATA_DIR = "/home/rpcuser/gate/system/devices/TRB3/data/daqData/asci"
START_DAQ_SCRIPT = "/home/rpcuser/trbsoft/userscripts/trb/startup_TRB399.sh"
STALE_FILE_THRESHOLD_S = 3 * 3600
SSH_BASE_CMD = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=5",
    "-o",
    "ConnectionAttempts=1",
]


def parse_mingo_hosts():
    hosts = []
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line.lower().startswith("host "):
                    continue
                names = line.split()[1:]
                for name in names:
                    if re.match(r"^mingo0\d+$", name):
                        hosts.append(name)
    except OSError:
        return []
    return sorted(set(hosts))


def check_host(host, process_name):
    if not process_name:
        return "red", "no process name set"
    cmd = SSH_BASE_CMD + [host, "pgrep", "-f", process_name]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        return "red", f"ssh error: {exc}"
    if result.returncode == 0:
        return "green", "connected, measurement running"
    if result.returncode == 1:
        return "orange", "connected, no measurement"
    return "red", f"ssh/pgrep error (rc={result.returncode})"


def get_station_id(host):
    match = re.search(r"mingo0(\d+)$", host)
    if not match:
        return None
    return match.group(1).zfill(2)


def format_age(seconds):
    if seconds is None:
        return None
    seconds = int(seconds)
    if seconds < 0:
        return "in future"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d {hours:02d}h"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    if minutes > 0:
        return f"{minutes}m {sec:02d}s"
    return f"{sec}s"


def get_latest_daq_file(host):
    station = get_station_id(host)
    if not station:
        return None, None, None, "station unknown"
    glob_path = f"{DAQ_DATA_DIR}/mi{station}*.dat*"
    remote_cmd = (
        f'glob_literal="{glob_path}"; '
        f"set -- {glob_path}; "
        'if [ "$1" = "$glob_literal" ] && [ ! -e "$1" ]; then exit 0; fi; '
        'latest=$(ls -1t -- "$@" 2>/dev/null); '
        "ls_rc=$?; "
        "if [ $ls_rc -ne 0 ]; then exit $ls_rc; fi; "
        'latest=$(printf "%s\n" "$latest" | head -n 1); '
        'if [ -n "$latest" ]; then '
        'now=$(date +%s); '
        'mtime=$(stat -c "%Y" "$latest" 2>/dev/null || stat -f "%m" "$latest" 2>/dev/null); '
        'if [ -n "$mtime" ]; then echo "$now $mtime $latest"; fi; '
        "fi"
    )
    cmd = SSH_BASE_CMD + [host, remote_cmd]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError as exc:
        return None, None, None, f"ssh error: {exc}"
    if result.returncode == 255:
        return None, None, None, "ssh error"
    output = result.stdout.strip()
    if not output:
        if result.returncode != 0:
            return None, None, None, f"command error (rc={result.returncode})"
        return None, None, None, "not found"
    parts = output.split(None, 2)
    if len(parts) != 3:
        return None, None, None, "parse error"
    try:
        remote_now_epoch = int(parts[0])
        mtime_epoch = int(parts[1])
    except ValueError:
        return None, None, None, "parse error"
    return os.path.basename(parts[2]), mtime_epoch, remote_now_epoch, None


def build_latest_file_info(host):
    filename, mtime_epoch, remote_now_epoch, error = get_latest_daq_file(host)
    if error == "not found":
        return "last file: not found", "no file", None
    if error:
        compact_error = "ssh error" if error.startswith("ssh error") else error
        return f"last file: {error}", compact_error, None
    age_seconds = int(remote_now_epoch - mtime_epoch)
    age_text = format_age(age_seconds)
    if age_text == "in future":
        return f"last file: {filename} (in future)", "in future", age_seconds
    return (
        f"last file: {filename} ({age_text} ago)",
        f"{age_text} ago",
        age_seconds,
    )


class HostRow:
    def __init__(self, parent, host, start_callback=None):
        self.host = host
        self.start_callback = start_callback
        self.compact = False
        self.current_color = "red"
        self.frame = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.frame, width=16, height=16, highlightthickness=0)
        self.indicator = self.canvas.create_oval(2, 2, 14, 14, fill="red", outline="")
        self.host_label = ttk.Label(self.frame, text=host, width=10)
        self.status_label = ttk.Label(self.frame, text="checking...")
        self.age_label = ttk.Label(self.frame, text="")
        self.file_label = ttk.Label(self.frame, text="", justify="left")
        self.start_button = ttk.Button(
            self.frame, text="Start DAQ", command=self._on_start
        )
        self.start_button.state(["disabled"])

        self.canvas.grid(row=0, column=0, padx=(0, 6))
        self.host_label.grid(row=0, column=1, sticky="w")
        self.status_label.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        self.start_button.grid(row=0, column=3, sticky="e", padx=(10, 0))
        self.file_label.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(2, 0))
        self.frame.grid_columnconfigure(2, weight=1)
        self.frame.grid_columnconfigure(3, weight=0)

    def grid(self, row):
        self.frame.grid(row=row, column=0, sticky="ew", pady=2)

    def set_status(self, color, text):
        self.current_color = color
        self.canvas.itemconfigure(self.indicator, fill=color)
        self.status_label.configure(text=text)
        self._sync_start_button()

    def set_file_info(self, full_text, compact_text):
        self.file_label.configure(text=full_text)
        self.age_label.configure(text=compact_text)

    def set_wrap_width(self, width):
        self.status_label.configure(wraplength=max(150, width - 240))
        self.file_label.configure(wraplength=max(150, width - 60))

    def set_compact(self, compact):
        self.compact = compact
        if compact:
            self.status_label.grid_remove()
            self.file_label.grid_remove()
            self.age_label.grid(row=0, column=2, sticky="w", padx=(8, 0))
            self.start_button.grid_remove()
            self.frame.grid_columnconfigure(1, weight=1)
            self.frame.grid_columnconfigure(2, weight=0)
        else:
            self.status_label.grid(row=0, column=2, sticky="ew", padx=(8, 0))
            self.start_button.grid(row=0, column=3, sticky="e", padx=(10, 0))
            self.file_label.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(2, 0))
            self.age_label.grid_remove()
            self.frame.grid_columnconfigure(1, weight=0)
            self.frame.grid_columnconfigure(2, weight=1)
        self._sync_start_button()

    def _sync_start_button(self):
        if self.compact:
            self.start_button.state(["disabled"])
            return
        if self.current_color == "purple":
            self.start_button.state(["!disabled"])
        else:
            self.start_button.state(["disabled"])

    def _on_start(self):
        if self.current_color != "purple":
            return
        if self.start_callback:
            self.start_callback(self.host)


class App:
    def __init__(self, root, hosts=None, process=None, interval=None):
        self.root = root
        self.root.title("miniTRASGO Status Monitor")
        self.root.resizable(True, True)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self.process_var = tk.StringVar(value=process or DEFAULT_PROCESS)
        self.interval_var = tk.StringVar(
            value=str(interval if interval is not None else DEFAULT_INTERVAL_S)
        )
        self.hosts_var = tk.StringVar(value=hosts or "")

        self.checking = False
        self.after_id = None
        self.compact_view = False

        self.host_rows = []
        self.hosts = []

        self._build_ui()
        self._load_default_hosts()
        self.apply_settings()

    def _build_ui(self):
        controls = ttk.Frame(self.root, padding=10)
        status_frame = ttk.Frame(self.root, padding=(10, 0, 10, 0))
        actions = ttk.Frame(self.root, padding=(10, 6, 10, 10))

        self.last_update_var = tk.StringVar(value="Updated: --")
        ttk.Label(status_frame, textvariable=self.last_update_var).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        ttk.Label(controls, text="Hosts (comma-separated):").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(controls, textvariable=self.hosts_var, width=40).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Label(controls, text="Process:").grid(row=1, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.process_var, width=20).grid(
            row=1, column=1, sticky="ew"
        )
        ttk.Label(controls, text="Interval (s):").grid(row=2, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.interval_var, width=10).grid(
            row=2, column=1, sticky="w"
        )

        ttk.Button(controls, text="Apply", command=self.apply_settings).grid(
            row=3, column=0, pady=(6, 0), sticky="w"
        )
        ttk.Button(controls, text="Check now", command=self.check_now).grid(
            row=3, column=1, pady=(6, 0), sticky="w"
        )
        # ttk.Button(controls, text="Help", command=self.show_help).grid(
        #     row=3, column=2, pady=(6, 0), sticky="w", padx=(10, 0),
        # )

        self.view_button = ttk.Button(
            actions, text="Compact view", command=self.toggle_view
        )
        self.view_button.grid(row=0, column=0, sticky="w")

        controls.grid_columnconfigure(1, weight=1)
        self.controls = controls
        self.status_frame = status_frame
        controls.grid(row=0, column=0, sticky="ew")
        status_frame.grid(row=1, column=0, sticky="nsew")
        actions.grid(row=2, column=0, sticky="ew")
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        width = self.status_frame.winfo_width()
        for row in self.host_rows:
            row.set_wrap_width(width)

    def toggle_view(self):
        self.compact_view = not self.compact_view
        if self.compact_view:
            self.controls.grid_remove()
            self.view_button.configure(text="Full view")
        else:
            self.controls.grid()
            self.view_button.configure(text="Compact view")
        for row in self.host_rows:
            row.set_compact(self.compact_view)
        self._resize_for_view()

    def _resize_for_view(self):
        width, height = FULL_VIEW_SIZE
        if self.compact_view:
            width, height = COMPACT_VIEW_SIZE
        self.root.update_idletasks()
        self.root.geometry(f"{width}x{height}")

    def show_help(self):
        threshold_text = format_age(STALE_FILE_THRESHOLD_S) or f"{STALE_FILE_THRESHOLD_S}s"
        message = (
            "Checks SSH connectivity to mingo0X hosts and whether the analysis "
            "process is running.\n\n"
            "Colors:\n"
            "- Red: not connected (SSH failed)\n"
            "- Orange: connected, process not running\n"
            f"- Purple: connected, process running but no file in last {threshold_text}\n"
            f"- Green: connected, process running and file in last {threshold_text}\n\n"
            "Tips:\n"
            "- Hosts: comma-separated SSH aliases (from ~/.ssh/config)\n"
            "- Process: match against full command (default dabc_exe)\n"
            "- Interval: seconds between checks (min 2s)\n"
            f"- Latest file: mi<station>*.dat* in {DAQ_DATA_DIR}"
        )
        messagebox.showinfo("Help", message, parent=self.root)

    def _load_default_hosts(self):
        if self.hosts_var.get().strip():
            return
        hosts = parse_mingo_hosts()
        if hosts:
            self.hosts_var.set(", ".join(hosts))

    def _parse_hosts(self):
        raw = self.hosts_var.get().strip()
        if not raw:
            return []
        return [h.strip() for h in raw.split(",") if h.strip()]

    def _rebuild_rows(self, hosts):
        for row in self.host_rows:
            row.frame.destroy()
        self.host_rows = []
        for i, host in enumerate(hosts):
            row = HostRow(self.status_frame, host, self.start_daq)
            row.grid(i + 1)
            row.set_compact(self.compact_view)
            self.host_rows.append(row)
        self.status_frame.grid_columnconfigure(0, weight=1)

    def apply_settings(self):
        hosts = self._parse_hosts()
        if not hosts:
            hosts = parse_mingo_hosts()
        if not hosts:
            hosts = ["mingo01"]

        if hosts != self.hosts:
            self.hosts = hosts
            self._rebuild_rows(hosts)

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.check_now()

    def _get_interval_ms(self):
        try:
            interval = int(self.interval_var.get().strip())
        except ValueError:
            interval = DEFAULT_INTERVAL_S
        if interval < 2:
            interval = 2
        return interval * 1000

    def check_now(self):
        if self.checking:
            return
        self.checking = True
        thread = threading.Thread(target=self._do_checks, daemon=True)
        thread.start()

    def _do_checks(self):
        process_name = self.process_var.get().strip()
        results = {}
        for host in self.hosts:
            status = check_host(host, process_name)
            full_text, compact_text, age_seconds = build_latest_file_info(host)
            results[host] = (status, full_text, compact_text, age_seconds)
        self.root.after(0, lambda: self._apply_results(results))

    def _apply_results(self, results):
        self.last_update_var.set(f"Updated: {time.strftime('%H:%M:%S')}")
        for row in self.host_rows:
            status, full_text, compact_text, age_seconds = results.get(
                row.host, (("red", "no result"), "last file: n/a", "n/a", None)
            )
            color, text = status
            if color == "green":
                if (
                    age_seconds is None
                    or age_seconds < 0
                    or age_seconds > STALE_FILE_THRESHOLD_S
                ):
                    color = "purple"
            row.set_status(color, text)
            row.set_file_info(full_text, compact_text)
        self.checking = False
        self.after_id = self.root.after(self._get_interval_ms(), self.check_now)

    def start_daq(self, host):
        thread = threading.Thread(target=self._start_daq_worker, args=(host,), daemon=True)
        thread.start()

    def _start_daq_worker(self, host):
        cmd = SSH_BASE_CMD + [host, START_DAQ_SCRIPT]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except OSError as exc:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Start DAQ", f"SSH error: {exc}", parent=self.root
                ),
            )
            return
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            detail = f"\n\n{stderr}" if stderr else ""
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Start DAQ",
                    f"Failed to start DAQ on {host} (rc={result.returncode}).{detail}",
                    parent=self.root,
                ),
            )
            return
        self.root.after(
            0,
            lambda: messagebox.showinfo(
                "Start DAQ", f"Start DAQ command sent to {host}.", parent=self.root
            ),
        )


def main():
    threshold_text = format_age(STALE_FILE_THRESHOLD_S) or f"{STALE_FILE_THRESHOLD_S}s"
    parser = argparse.ArgumentParser(
        description=(
            "GUI monitor for mingo0X hosts that checks SSH connectivity and whether "
            "the analysis process is running."
        ),
        epilog=(
            "Status colors: red=not connected, orange=connected/no measurement, "
            f"purple=connected/measurement but no recent file (missing or older than {threshold_text}), "
            f"green=connected/measurement with recent file (age <= {threshold_text})."
        ),
    )
    parser.add_argument(
        "--hosts",
        default="",
        help="Comma-separated SSH aliases (default: auto-detect mingo0X from ~/.ssh/config)",
    )
    parser.add_argument(
        "--process",
        default=DEFAULT_PROCESS,
        help=f"Process match for pgrep -f (default: {DEFAULT_PROCESS})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_S,
        help=f"Seconds between checks (min 2s, default: {DEFAULT_INTERVAL_S})",
    )
    args = parser.parse_args()

    root = tk.Tk()
    ttk.Style().theme_use("clam")
    app = App(root, hosts=args.hosts, process=args.process, interval=args.interval)
    root.mainloop()


if __name__ == "__main__":
    main()
