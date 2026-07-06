#!/usr/bin/env python3
"""MINGO Cron Log Matrix Viewer.

Read-only matrix view over selected DATAFLOW_v3 cron logs. The only file this
program writes is its own layout/configuration JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk


APP_TITLE = "MINGO Cron Log Matrix Viewer"
DEFAULT_DATAFLOW_ROOT = "/home/mingo/DATAFLOW_v3"
DEFAULT_CRON_LOG_ROOT = (
    "/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/CRON_LOGS"
)
DEFAULT_CONFIG = (
    "/home/mingo/DATAFLOW_v3/OPERATIONS/OPERATIONS_RUNTIME/GUI_CONFIGS/"
    "mingo_cron_log_matrix_layout.json"
)
FALLBACK_CONFIG = "~/.config/mingo_cron_logs/layout.json"
STATIONS = ["global", "0", "1", "2", "3", "4"]
STATION_LABELS = {
    "global": "Global",
    "0": "Station 0",
    "1": "Station 1",
    "2": "Station 2",
    "3": "Station 3",
    "4": "Station 4",
}
CATEGORIES = [
    "Critical",
    "Stage 0",
    "Stage 1",
    "Stage 2",
    "Reprocessing",
    "Simulation",
    "Plotters",
    "Ancillary / Operations",
    "Station sync",
]
SUSPICIOUS_PATTERNS = [
    "Traceback",
    "ERROR",
    "CRITICAL",
    "Exception",
    "FAILED",
    "WARNING",
    "lock busy",
    "resource gate",
    "no such file",
    "permission denied",
    "killed",
    "out of memory",
    "stale lock",
    "rsync error",
]


@dataclass(frozen=True)
class ScriptEntry:
    key: str
    label: str
    category: str
    frequency: str
    paths: dict[str, str]


def station_paths(template: str, stations: tuple[str, ...] = ("1", "2", "3", "4")) -> dict[str, str]:
    return {station: template.format(station=station, station2=f"{int(station):02d}") for station in stations}


MANIFEST = [
    ScriptEntry(
        "error_finder",
        "Error finder",
        "Critical",
        "critical",
        {"global": "ANCILLARY/OPERATIONS/SEARCH_FOR_ERRORS/error_finder.log"},
    ),
    ScriptEntry(
        "cron_bootstrap",
        "Cron bootstrap",
        "Critical",
        "critical",
        {"global": "ANCILLARY/OPERATIONS/CRON_BOOTSTRAP/cron_bootstrap.log"},
    ),
    ScriptEntry(
        "crontab_install",
        "Crontab install",
        "Critical",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/CRON_BOOTSTRAP/crontab_install.log"},
    ),
    ScriptEntry(
        "bring_new_files",
        "Bring new files",
        "Stage 0",
        "critical",
        station_paths("MAIN_ANALYSIS/STAGE_0/NEW_FILES/bring_data_and_config_files_{station}.log"),
    ),
    ScriptEntry(
        "prepare_reprocessing_metadata",
        "Prepare reprocessing metadata",
        "Reprocessing",
        "daily",
        station_paths("MAIN_ANALYSIS/STAGE_0/REPROCESSING/STEP_0/log_prepare_reprocessing_metadata_{station}.log"),
    ),
    ScriptEntry(
        "bring_reprocessing_files",
        "Bring reprocessing files",
        "Reprocessing",
        "daily",
        station_paths("MAIN_ANALYSIS/STAGE_0/REPROCESSING/STEP_1/log_bring_reprocessing_files_{station}.log"),
    ),
    ScriptEntry(
        "unpack_reprocessing_files",
        "Unpack reprocessing files",
        "Reprocessing",
        "daily",
        station_paths("MAIN_ANALYSIS/STAGE_0/REPROCESSING/STEP_2/log_unpack_reprocessing_files_{station}.log"),
    ),
    ScriptEntry(
        "copernicus_bring",
        "Copernicus bring",
        "Stage 1",
        "hourly",
        station_paths("MAIN_ANALYSIS/STAGE_1/COPERNICUS/copernicus_bring_{station}.log"),
    ),
    ScriptEntry(
        "raw_to_corrected",
        "Raw to corrected",
        "Stage 1",
        "critical",
        station_paths(
            "MAIN_ANALYSIS/STAGE_1/EVENT_DATA/STEP_1/guide_raw_to_corrected_{station}.log",
            ("0", "1", "2", "3", "4"),
        ),
    ),
    ScriptEntry(
        "lab_logs_bring_and_clean",
        "Lab logs bring and clean",
        "Stage 1",
        "hourly",
        station_paths("MAIN_ANALYSIS/STAGE_1/LOG_DATA/STEP_1/lab_logs_bring_and_clean_{station}.log"),
    ),
    ScriptEntry(
        "lab_logs_merge",
        "Lab logs merge",
        "Stage 1",
        "hourly",
        station_paths("MAIN_ANALYSIS/STAGE_1/LOG_DATA/STEP_2/lab_logs_merge_{station}.log"),
    ),
    ScriptEntry(
        "build_stage_2_dataset",
        "Build Stage 2 dataset",
        "Stage 2",
        "hourly",
        station_paths("MAIN_ANALYSIS/STAGE_2/build_stage_2_dataset_{station}.log"),
    ),
    ScriptEntry(
        "station_automation_scripts_update",
        "Station automation scripts update",
        "Station sync",
        "daily",
        station_paths("ANCILLARY/REMOTE_SYNC/STATION_AUTOMATION_SCRIPTS/update_mingo{station2}.log"),
    ),
    ScriptEntry(
        "sim_main_pipeline_cycle",
        "Simulation main cycle",
        "Simulation",
        "hourly",
        {"global": "SIMULATION/RUN/sim_main_pipeline_cycle.log"},
    ),
    ScriptEntry(
        "step_final_cron",
        "Simulation STEP_FINAL",
        "Simulation",
        "daily",
        {"global": "SIMULATION/STEP_FINAL/step_final_cron.log"},
    ),
    ScriptEntry(
        "metadata_plots",
        "Metadata plots",
        "Plotters",
        "daily",
        {"global": "PLOTTERS/create_metadata_plots.log"},
    ),
    ScriptEntry(
        "quick_check_pdf_sync",
        "Quick-check PDF sync",
        "Plotters",
        "hourly",
        {"global": "PLOTTERS/QUICK_CHECK_PLOTS/sync_latest_step1_pdfs.log"},
    ),
    ScriptEntry(
        "run_simulation_plots",
        "Simulation plots",
        "Plotters",
        "daily",
        {"global": "PLOTTERS/run_simulation_plots.log"},
    ),
    ScriptEntry(
        "solve_stale_locks",
        "Solve stale locks",
        "Ancillary / Operations",
        "hourly",
        {"global": "ANCILLARY/OPERATIONS/SOLVE_STALE_LOCKS/solve_stale_locks.cron.log"},
    ),
    ScriptEntry(
        "watchdog_process_counts",
        "Watchdog process counts",
        "Ancillary / Operations",
        "critical",
        {"global": "ANCILLARY/OPERATIONS/WATCHDOG_PROCESS_COUNTS/watchdog_process_counts.cron.log"},
    ),
    ScriptEntry(
        "flush_from_unprocessed",
        "Flush from unprocessed",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/FLUSH_FROM_UNPROCESSED/flush_from_unprocessed.log"},
    ),
    ScriptEntry(
        "fix_event_metadata_files",
        "Fix event metadata files",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/FIX_METADATA_FILES/fix_event_metadata_files.log"},
    ),
    ScriptEntry(
        "update_execution_csvs",
        "Update execution CSVs",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/UPDATE_EXECUTION_CSVS/update_execution_csvs.log"},
    ),
    ScriptEntry(
        "generate_columns_review",
        "Generate columns review",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/FOLLOW_COLUMNS/generate_columns_review.log"},
    ),
    ScriptEntry(
        "persistent_telegram_bot",
        "Persistent Telegram bot",
        "Ancillary / Operations",
        "critical",
        {"global": "ANCILLARY/TELEGRAM_BOT/cron_persistent_telegram_bot.log"},
    ),
    ScriptEntry(
        "remote_log_backup",
        "Remote log backup",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/REMOTE_LOG_BACKUP/log_backup.cron.log"},
    ),
    ScriptEntry(
        "update_plots",
        "Update documentation plots",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/UPDATE_PLOTS/update_plots.log"},
    ),
    ScriptEntry(
        "ensure_cron_log_paths",
        "Ensure cron log paths",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/ENSURE_CRON_LOG_PATHS/ensure_cron_log_paths.log"},
    ),
    ScriptEntry(
        "erase_cron_logs",
        "Erase cron logs",
        "Ancillary / Operations",
        "daily",
        {"global": "ANCILLARY/OPERATIONS/ERASE_ALL_CRON_LOGS/erase_cron_logs.log"},
    ),
    ScriptEntry(
        "auto_clear_swap",
        "Auto-clear swap",
        "Ancillary / Operations",
        "critical",
        {"global": "ANCILLARY/OPERATIONS/AUTO_CLEAR_SWAP/auto_clear_swap_if_idle.log"},
    ),
]
MANIFEST_BY_KEY = {entry.key: entry for entry in MANIFEST}


BUILTIN_LAYOUT = {
    "version": 1,
    "selected_stations": ["global", "1", "2", "3", "4"],
    "selected_scripts": [
        "error_finder",
        "cron_bootstrap",
        "bring_new_files",
        "raw_to_corrected",
        "lab_logs_bring_and_clean",
        "lab_logs_merge",
        "copernicus_bring",
        "build_stage_2_dataset",
        "sim_main_pipeline_cycle",
        "step_final_cron",
        "metadata_plots",
        "quick_check_pdf_sync",
        "solve_stale_locks",
        "watchdog_process_counts",
    ],
    "tail_lines": 200,
    "refresh_interval_seconds": 30,
    "auto_refresh": True,
    "auto_scroll": True,
    "show_inactive_entries": False,
    "status_age_thresholds_minutes": {"critical": 15, "hourly": 90, "daily": 1800},
}


def deep_copy_layout(layout: dict) -> dict:
    return json.loads(json.dumps(layout))


def merge_layout(base: dict, loaded: dict) -> dict:
    merged = deep_copy_layout(base)
    for key, value in loaded.items():
        if key == "status_age_thresholds_minutes" and isinstance(value, dict):
            merged[key].update(value)
        else:
            merged[key] = value
    merged["selected_stations"] = [s for s in merged.get("selected_stations", []) if s in STATIONS]
    merged["selected_scripts"] = [
        s for s in merged.get("selected_scripts", []) if s in MANIFEST_BY_KEY
    ]
    if not merged["selected_stations"]:
        merged["selected_stations"] = list(BUILTIN_LAYOUT["selected_stations"])
    if not merged["selected_scripts"]:
        merged["selected_scripts"] = list(BUILTIN_LAYOUT["selected_scripts"])
    merged["tail_lines"] = max(1, int(merged.get("tail_lines", 200)))
    merged["refresh_interval_seconds"] = max(5, int(merged.get("refresh_interval_seconds", 30)))
    return merged


def format_age(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 90:
        return f"{int(seconds)}s"
    minutes = seconds / 60
    if minutes < 90:
        return f"{int(minutes)}m"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def read_last_lines(path: Path, line_count: int, max_bytes: int = 2_000_000) -> list[str]:
    if line_count <= 0:
        return []
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        end = handle.tell()
        size = min(end, max_bytes)
        handle.seek(end - size)
        data = handle.read(size)
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()[-line_count:]


def suspicious_lines(lines: list[str]) -> list[str]:
    lowered_patterns = [pattern.lower() for pattern in SUSPICIOUS_PATTERNS]
    matches = []
    for line in lines:
        lower = line.lower()
        if any(pattern.lower() in lower for pattern in lowered_patterns):
            matches.append(line)
    return matches


class LayoutConfig:
    def __init__(self, requested_path: str):
        self.primary_path = Path(requested_path).expanduser()
        self.fallback_path = Path(FALLBACK_CONFIG).expanduser()
        self.active_path = self.primary_path

    def choose_read_path(self) -> Path | None:
        if self.primary_path.exists():
            return self.primary_path
        if self.fallback_path.exists():
            self.active_path = self.fallback_path
            return self.fallback_path
        return None

    def load(self) -> tuple[dict, str]:
        path = self.choose_read_path()
        if path is None:
            return deep_copy_layout(BUILTIN_LAYOUT), "Using built-in layout; no config file exists yet."
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            self.active_path = path
            return merge_layout(BUILTIN_LAYOUT, loaded), f"Loaded layout from {path}"
        except Exception as exc:
            return deep_copy_layout(BUILTIN_LAYOUT), f"Failed to load {path}: {exc}. Using built-in layout."

    def save(self, layout: dict) -> tuple[bool, str]:
        for path in (self.active_path, self.primary_path, self.fallback_path):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8") as handle:
                    json.dump(layout, handle, indent=2, sort_keys=False)
                    handle.write("\n")
                self.active_path = path
                return True, f"Saved default layout to {path}"
            except Exception:
                continue
        return False, f"Could not write {self.primary_path} or {self.fallback_path}"


class TailTab:
    def __init__(self, app: "CronLogMatrixApp", path: Path, title: str, lines: int):
        self.app = app
        self.path = path
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.running = True
        self.frame = ttk.Frame(app.tail_notebook, padding=6)
        self.auto_scroll = tk.BooleanVar(value=app.auto_scroll_var.get())
        app.tail_notebook.add(self.frame, text=title[:24])
        app.tail_notebook.select(self.frame)

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Stop", command=self.stop).pack(side="left")
        ttk.Button(bar, text="Copy path", command=self.copy_path).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Copy visible text", command=self.copy_text).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Clear view", command=self.clear).pack(side="left", padx=(4, 0))
        ttk.Checkbutton(bar, text="Auto-scroll", variable=self.auto_scroll).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Close tab", command=self.close).pack(side="right")

        self.text = tk.Text(self.frame, wrap="none", height=12, font=("TkFixedFont", 10))
        yscroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.text.yview)
        xscroll = ttk.Scrollbar(self.frame, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.text.tag_configure("suspicious", foreground="#b00020")

        self.thread = threading.Thread(target=self._run_tail, args=(lines,), daemon=True)
        self.thread.start()
        self._poll()

    def _run_tail(self, lines: int) -> None:
        try:
            self.process = subprocess.Popen(
                ["tail", "-n", str(lines), "-F", str(self.path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                if not self.running:
                    break
                self.queue.put(line)
        except Exception as exc:
            self.queue.put(f"[tail failed] {exc}\n")
        finally:
            self.queue.put(None)

    def _poll(self) -> None:
        while True:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                self.running = False
                continue
            tag = "suspicious" if suspicious_lines([item]) else None
            self.text.insert("end", item, tag)
            if self.auto_scroll.get():
                self.text.see("end")
        if self.running:
            self.app.root.after(150, self._poll)

    def stop(self) -> None:
        self.running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.text.insert("end", "\n[tail stopped]\n")
        self.text.see("end")

    def close(self) -> None:
        self.stop()
        self.app.tail_notebook.forget(self.frame)
        self.app.tail_tabs.pop(self.path, None)

    def copy_path(self) -> None:
        self.app.copy_to_clipboard(str(self.path))

    def copy_text(self) -> None:
        self.app.copy_to_clipboard(self.text.get("1.0", "end-1c"))

    def clear(self) -> None:
        self.text.delete("1.0", "end")


class CronLogMatrixApp:
    def __init__(self, root: tk.Tk, args: argparse.Namespace):
        self.root = root
        self.args = args
        self.cron_log_root = Path(args.cron_log_root).expanduser()
        self.config = LayoutConfig(args.config)
        self.layout, status = self.config.load()
        if args.reset_layout:
            self.layout = deep_copy_layout(BUILTIN_LAYOUT)
        if args.lines is not None:
            self.layout["tail_lines"] = args.lines
        if args.refresh_interval is not None:
            self.layout["refresh_interval_seconds"] = max(5, args.refresh_interval)
        if args.include_inactive:
            self.layout["show_inactive_entries"] = True
        if args.no_auto_refresh:
            self.layout["auto_refresh"] = False

        self.selected_stations = list(self.layout["selected_stations"])
        self.selected_scripts = list(self.layout["selected_scripts"])
        self.cell_labels: dict[tuple[str, str], ttk.Label] = {}
        self.cell_status: dict[tuple[str, str], dict] = {}
        self.selected_cell: tuple[str, str] | None = None
        self.tail_tabs: dict[Path, TailTab] = {}

        self.tail_lines_var = tk.IntVar(value=int(self.layout["tail_lines"]))
        self.refresh_interval_var = tk.IntVar(value=int(self.layout["refresh_interval_seconds"]))
        self.auto_refresh_var = tk.BooleanVar(value=bool(self.layout["auto_refresh"]))
        self.auto_scroll_var = tk.BooleanVar(value=bool(self.layout["auto_scroll"]))
        self.show_inactive_var = tk.BooleanVar(value=bool(self.layout["show_inactive_entries"]))
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value=status)

        self.root.title(APP_TITLE)
        self.root.geometry("1380x860")
        self._build_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_matrix()
        self._schedule_refresh()

    def _build_style(self) -> None:
        style = ttk.Style()
        style.configure("Status.OK.TLabel", background="#dff0d8", foreground="#144d14", padding=5)
        style.configure("Status.WARN.TLabel", background="#fff1bf", foreground="#6b4c00", padding=5)
        style.configure("Status.ERROR.TLabel", background="#ffd6d6", foreground="#7f0000", padding=5)
        style.configure("Status.MISSING.TLabel", background="#e0e0e0", foreground="#333333", padding=5)
        style.configure("Status.NA.TLabel", background="#f4f4f4", foreground="#777777", padding=5)
        style.configure("RowHeader.TLabel", padding=5, font=("TkDefaultFont", 9, "bold"))

    def _build_ui(self) -> None:
        self._build_menu()
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Stations", command=self.open_station_selector).pack(side="left")
        ttk.Button(top, text="Scripts", command=self.open_script_selector).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Tail lines").pack(side="left")
        ttk.Spinbox(top, from_=10, to=20000, increment=10, width=7, textvariable=self.tail_lines_var).pack(side="left", padx=(4, 10))
        ttk.Label(top, text="Refresh seconds").pack(side="left")
        ttk.Spinbox(top, from_=5, to=3600, increment=5, width=7, textvariable=self.refresh_interval_var).pack(side="left", padx=(4, 10))
        ttk.Checkbutton(top, text="Auto-refresh", variable=self.auto_refresh_var).pack(side="left")
        ttk.Checkbutton(top, text="Auto-scroll", variable=self.auto_scroll_var).pack(side="left", padx=(4, 10))
        ttk.Checkbutton(top, text="Show inactive", variable=self.show_inactive_var, command=self.rebuild_matrix).pack(side="left")
        ttk.Button(top, text="Refresh matrix", command=self.refresh_matrix).pack(side="left", padx=(12, 0))
        ttk.Button(top, text="Follow selected", command=self.follow_selected).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="Stop all tails", command=self.stop_all_tails).pack(side="left", padx=(4, 0))
        ttk.Button(top, text="Set current layout as default", command=self.save_current_layout).pack(side="right")

        search_row = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        search_row.pack(fill="x")
        ttk.Label(search_row, text="Filter").pack(side="left")
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=48)
        search_entry.pack(side="left", padx=(4, 8))
        search_entry.bind("<KeyRelease>", lambda _event: self.rebuild_matrix())
        ttk.Button(search_row, text="Clear", command=lambda: (self.search_var.set(""), self.rebuild_matrix())).pack(side="left")
        ttk.Label(search_row, textvariable=self.status_var).pack(side="right")

        main_pane = ttk.PanedWindow(self.root, orient="vertical")
        main_pane.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        matrix_frame = ttk.Frame(main_pane)
        self.canvas = tk.Canvas(matrix_frame, highlightthickness=0)
        vscroll = ttk.Scrollbar(matrix_frame, orient="vertical", command=self.canvas.yview)
        hscroll = ttk.Scrollbar(matrix_frame, orient="horizontal", command=self.canvas.xview)
        self.matrix_inner = ttk.Frame(self.canvas)
        self.matrix_inner.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.matrix_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")
        hscroll.pack(side="bottom", fill="x")
        main_pane.add(matrix_frame, weight=3)

        bottom = ttk.PanedWindow(main_pane, orient="horizontal")
        preview_frame = ttk.Frame(bottom, padding=6)
        ttk.Label(preview_frame, text="Selected log preview").pack(anchor="w")
        self.preview_meta = ttk.Label(preview_frame, text="", justify="left")
        self.preview_meta.pack(anchor="w", fill="x", pady=(0, 4))
        self.preview_text = tk.Text(preview_frame, wrap="none", height=13, font=("TkFixedFont", 10))
        self.preview_text.tag_configure("suspicious", foreground="#b00020")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")

        tails_frame = ttk.Frame(bottom, padding=6)
        ttk.Label(tails_frame, text="Live tails").pack(anchor="w")
        self.tail_notebook = ttk.Notebook(tails_frame)
        self.tail_notebook.pack(fill="both", expand=True)

        bottom.add(preview_frame, weight=1)
        bottom.add(tails_frame, weight=1)
        main_pane.add(bottom, weight=2)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        settings = tk.Menu(menubar, tearoff=False)
        settings.add_command(label="Load default layout", command=self.load_default_layout)
        settings.add_command(label="Reset to built-in layout", command=self.reset_builtin_layout)
        settings.add_command(label="Set current layout as default", command=self.save_current_layout)
        settings.add_separator()
        settings.add_command(label="Open config file path", command=self.open_config_editor)
        settings.add_command(label="Reload config from disk", command=self.reload_config)
        menubar.add_cascade(label="Settings", menu=settings)
        self.root.config(menu=menubar)

    def current_layout(self) -> dict:
        return {
            "version": 1,
            "selected_stations": list(self.selected_stations),
            "selected_scripts": list(self.selected_scripts),
            "tail_lines": int(self.tail_lines_var.get()),
            "refresh_interval_seconds": max(5, int(self.refresh_interval_var.get())),
            "auto_refresh": bool(self.auto_refresh_var.get()),
            "auto_scroll": bool(self.auto_scroll_var.get()),
            "show_inactive_entries": bool(self.show_inactive_var.get()),
            "status_age_thresholds_minutes": dict(self.layout.get("status_age_thresholds_minutes", {})),
        }

    def save_current_layout(self) -> None:
        layout = self.current_layout()
        ok, message = self.config.save(layout)
        self.layout = merge_layout(BUILTIN_LAYOUT, layout)
        self.status_var.set(message)
        if ok:
            messagebox.showinfo(APP_TITLE, message)
        else:
            messagebox.showerror(APP_TITLE, message)

    def load_default_layout(self) -> None:
        self.layout, message = self.config.load()
        self.apply_layout(self.layout)
        self.status_var.set(message)

    def reload_config(self) -> None:
        self.load_default_layout()

    def reset_builtin_layout(self) -> None:
        self.apply_layout(deep_copy_layout(BUILTIN_LAYOUT))
        self.status_var.set("Reset to built-in layout. Use Set current layout as default to save it.")

    def apply_layout(self, layout: dict) -> None:
        self.layout = merge_layout(BUILTIN_LAYOUT, layout)
        self.selected_stations = list(self.layout["selected_stations"])
        self.selected_scripts = list(self.layout["selected_scripts"])
        self.tail_lines_var.set(int(self.layout["tail_lines"]))
        self.refresh_interval_var.set(int(self.layout["refresh_interval_seconds"]))
        self.auto_refresh_var.set(bool(self.layout["auto_refresh"]))
        self.auto_scroll_var.set(bool(self.layout["auto_scroll"]))
        self.show_inactive_var.set(bool(self.layout["show_inactive_entries"]))
        self.rebuild_matrix()
        self.refresh_matrix()

    def open_config_editor(self) -> None:
        path = self.config.active_path
        editor = tk.Toplevel(self.root)
        editor.title(f"Config: {path}")
        editor.geometry("900x650")
        ttk.Label(editor, text=str(path)).pack(anchor="w", padx=8, pady=(8, 0))
        text = tk.Text(editor, wrap="none", font=("TkFixedFont", 10))
        text.pack(fill="both", expand=True, padx=8, pady=8)
        if path.exists():
            try:
                text.insert("1.0", path.read_text(encoding="utf-8"))
            except Exception as exc:
                text.insert("1.0", f"Could not read {path}: {exc}\n")
        else:
            text.insert("1.0", json.dumps(self.current_layout(), indent=2) + "\n")

        def save_and_reload() -> None:
            try:
                loaded = json.loads(text.get("1.0", "end-1c"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(loaded, indent=2) + "\n", encoding="utf-8")
                self.config.active_path = path
                self.apply_layout(loaded)
                self.status_var.set(f"Saved and loaded config {path}")
                editor.destroy()
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"Could not save config:\n{exc}")

        buttons = ttk.Frame(editor, padding=8)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save and reload", command=save_and_reload).pack(side="right")
        ttk.Button(buttons, text="Close", command=editor.destroy).pack(side="right", padx=(0, 6))

    def rebuild_matrix(self) -> None:
        for child in self.matrix_inner.winfo_children():
            child.destroy()
        self.cell_labels.clear()
        filter_text = self.search_var.get().strip().lower()

        ttk.Label(self.matrix_inner, text="Script / task", style="RowHeader.TLabel").grid(row=0, column=0, sticky="nsew")
        for col, station in enumerate(self.selected_stations, start=1):
            ttk.Label(self.matrix_inner, text=STATION_LABELS[station], style="RowHeader.TLabel").grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

        row_index = 1
        for key in self.selected_scripts:
            entry = MANIFEST_BY_KEY.get(key)
            if not entry:
                continue
            haystack = " ".join([entry.key, entry.label, entry.category, *entry.paths.values()]).lower()
            if filter_text and filter_text not in haystack:
                continue
            ttk.Label(
                self.matrix_inner,
                text=f"{entry.label}\n{entry.category}",
                style="RowHeader.TLabel",
                justify="left",
            ).grid(row=row_index, column=0, sticky="nsew", padx=1, pady=1)
            for col, station in enumerate(self.selected_stations, start=1):
                label = ttk.Label(self.matrix_inner, text="", width=22, anchor="center", justify="center")
                label.grid(row=row_index, column=col, sticky="nsew", padx=1, pady=1)
                label.bind("<Button-1>", lambda _e, k=key, s=station: self.select_cell(k, s))
                label.bind("<Double-Button-1>", lambda _e, k=key, s=station: self.open_last_lines(k, s))
                label.bind("<Button-3>", lambda e, k=key, s=station: self.show_cell_menu(e, k, s))
                self.cell_labels[(key, station)] = label
            row_index += 1

        for col in range(len(self.selected_stations) + 1):
            self.matrix_inner.columnconfigure(col, weight=1)
        self.refresh_matrix()

    def refresh_matrix(self) -> None:
        if not self.cell_labels:
            self.rebuild_matrix()
            return
        for (key, station), label in self.cell_labels.items():
            status = self.compute_cell_status(key, station)
            self.cell_status[(key, station)] = status
            label.configure(text=status["text"], style=f"Status.{status['style']}.TLabel")
        self.status_var.set(f"Refreshed {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if self.selected_cell:
            self.select_cell(*self.selected_cell)

    def compute_cell_status(self, key: str, station: str) -> dict:
        entry = MANIFEST_BY_KEY[key]
        rel = entry.paths.get(station)
        if rel is None:
            return {"state": "NA", "style": "NA", "text": "N/A", "path": None, "relative": None}
        path = self.cron_log_root / rel
        data = {"path": path, "relative": rel, "entry": entry}
        try:
            stat = path.stat()
        except FileNotFoundError:
            return data | {"state": "MISSING", "style": "MISSING", "text": "MISSING\n-", "age": None, "size": 0, "suspicious": []}
        except Exception as exc:
            return data | {"state": "ERROR", "style": "ERROR", "text": f"ERROR\n{exc}", "age": None, "size": 0, "suspicious": []}
        age = time.time() - stat.st_mtime
        if stat.st_size == 0:
            return data | {"state": "EMPTY", "style": "WARN", "text": f"EMPTY\n{format_age(age)}", "age": age, "size": stat.st_size, "mtime": stat.st_mtime, "suspicious": []}
        lines = []
        try:
            lines = read_last_lines(path, int(self.tail_lines_var.get()))
        except Exception as exc:
            return data | {"state": "ERROR", "style": "ERROR", "text": f"ERROR\n{exc}", "age": age, "size": stat.st_size, "mtime": stat.st_mtime, "suspicious": []}
        suspicious = suspicious_lines(lines)
        if suspicious:
            last = suspicious[-1].strip()[:42]
            return data | {"state": "ERROR", "style": "ERROR", "text": f"ERROR\n{format_age(age)}\n{last}", "age": age, "size": stat.st_size, "mtime": stat.st_mtime, "suspicious": suspicious}
        thresholds = self.layout.get("status_age_thresholds_minutes", {})
        threshold = int(thresholds.get(entry.frequency, thresholds.get("hourly", 90))) * 60
        if age > threshold:
            return data | {"state": "OLD", "style": "WARN", "text": f"OLD\n{format_age(age)}", "age": age, "size": stat.st_size, "mtime": stat.st_mtime, "suspicious": []}
        return data | {"state": "OK", "style": "OK", "text": f"OK\n{format_age(age)}", "age": age, "size": stat.st_size, "mtime": stat.st_mtime, "suspicious": []}

    def select_cell(self, key: str, station: str) -> None:
        self.selected_cell = (key, station)
        status = self.cell_status.get((key, station)) or self.compute_cell_status(key, station)
        path = status.get("path")
        if path is None:
            self.preview_meta.configure(text=f"{MANIFEST_BY_KEY[key].label} / {STATION_LABELS[station]}\nN/A for this station.")
            self.preview_text.delete("1.0", "end")
            return
        self.preview_meta.configure(text=self.metadata_text(status))
        self.preview_text.delete("1.0", "end")
        try:
            lines = read_last_lines(path, int(self.tail_lines_var.get()))
        except Exception as exc:
            lines = [f"Could not read {path}: {exc}"]
        for line in lines:
            tag = "suspicious" if suspicious_lines([line]) else None
            self.preview_text.insert("end", line + "\n", tag)
        if self.auto_scroll_var.get():
            self.preview_text.see("end")

    def metadata_text(self, status: dict) -> str:
        path = status.get("path")
        mtime = status.get("mtime")
        mtime_text = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else "-"
        return (
            f"Absolute: {path}\n"
            f"Relative: {status.get('relative')}\n"
            f"exists: {Path(path).exists()} | size: {status.get('size', '-')} bytes | "
            f"mtime: {mtime_text} | age: {format_age(status.get('age'))} | "
            f"status: {status.get('state')} | suspicious lines in tail: {len(status.get('suspicious', []))}"
        )

    def show_cell_menu(self, event: tk.Event, key: str, station: str) -> None:
        self.select_cell(key, station)
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Open last lines", command=lambda: self.open_last_lines(key, station))
        menu.add_command(label="Follow live", command=lambda: self.follow_cell(key, station))
        menu.add_command(label="Copy path", command=lambda: self.copy_cell_path(key, station))
        menu.add_command(label="Refresh this cell", command=lambda: self.refresh_one_cell(key, station))
        menu.tk_popup(event.x_root, event.y_root)

    def open_last_lines(self, key: str, station: str) -> None:
        self.select_cell(key, station)

    def refresh_one_cell(self, key: str, station: str) -> None:
        status = self.compute_cell_status(key, station)
        self.cell_status[(key, station)] = status
        label = self.cell_labels.get((key, station))
        if label:
            label.configure(text=status["text"], style=f"Status.{status['style']}.TLabel")
        self.select_cell(key, station)

    def copy_cell_path(self, key: str, station: str) -> None:
        status = self.cell_status.get((key, station)) or self.compute_cell_status(key, station)
        path = status.get("path")
        self.copy_to_clipboard(str(path) if path else "N/A")

    def follow_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showinfo(APP_TITLE, "Select a log cell first.")
            return
        self.follow_cell(*self.selected_cell)

    def follow_cell(self, key: str, station: str) -> None:
        status = self.cell_status.get((key, station)) or self.compute_cell_status(key, station)
        path = status.get("path")
        if path is None:
            messagebox.showinfo(APP_TITLE, "This cell is N/A and has no log path.")
            return
        if path in self.tail_tabs:
            self.tail_notebook.select(self.tail_tabs[path].frame)
            return
        title = key if station == "global" else f"{key} S{station}"
        self.tail_tabs[path] = TailTab(self, path, title, int(self.tail_lines_var.get()))

    def stop_all_tails(self) -> None:
        for tab in list(self.tail_tabs.values()):
            tab.stop()

    def copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Copied to clipboard.")

    def open_station_selector(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Select stations")
        dialog.transient(self.root)
        vars_by_station = {s: tk.BooleanVar(value=s in self.selected_stations) for s in STATIONS}
        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)
        for station in STATIONS:
            ttk.Checkbutton(body, text=STATION_LABELS[station], variable=vars_by_station[station]).pack(anchor="w")

        def apply() -> None:
            selected = [s for s in STATIONS if vars_by_station[s].get()]
            if not selected:
                messagebox.showerror(APP_TITLE, "Select at least one station column.")
                return
            self.selected_stations = selected
            self.rebuild_matrix()
            dialog.destroy()

        buttons = ttk.Frame(dialog, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Set current layout as default", command=lambda: (apply(), self.save_current_layout())).pack(side="left")
        ttk.Button(buttons, text="Apply", command=apply).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(0, 6))

    def open_script_selector(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Select scripts")
        dialog.geometry("720x760")
        search = tk.StringVar()
        vars_by_key = {entry.key: tk.BooleanVar(value=entry.key in self.selected_scripts) for entry in MANIFEST}

        top = ttk.Frame(dialog, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        ttk.Entry(top, textvariable=search).pack(side="left", fill="x", expand=True, padx=4)

        canvas = tk.Canvas(dialog, highlightthickness=0)
        scroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", pady=8)

        def render() -> None:
            for child in inner.winfo_children():
                child.destroy()
            needle = search.get().lower().strip()
            for category in CATEGORIES:
                entries = [e for e in MANIFEST if e.category == category]
                if needle:
                    entries = [
                        e
                        for e in entries
                        if needle in " ".join([e.key, e.label, e.category, *e.paths.values()]).lower()
                    ]
                if not entries:
                    continue
                frame = ttk.LabelFrame(inner, text=category, padding=6)
                frame.pack(fill="x", expand=True, pady=(0, 8))
                actions = ttk.Frame(frame)
                actions.pack(fill="x")
                ttk.Button(actions, text="Select all", command=lambda es=entries: [vars_by_key[e.key].set(True) for e in es]).pack(side="left")
                ttk.Button(actions, text="Clear", command=lambda es=entries: [vars_by_key[e.key].set(False) for e in es]).pack(side="left", padx=4)
                for entry in entries:
                    ttk.Checkbutton(frame, text=f"{entry.label}  ({entry.key})", variable=vars_by_key[entry.key]).pack(anchor="w")

        search.trace_add("write", lambda *_args: render())
        render()

        def apply() -> None:
            selected = [entry.key for entry in MANIFEST if vars_by_key[entry.key].get()]
            if not selected:
                messagebox.showerror(APP_TITLE, "Select at least one script row.")
                return
            self.selected_scripts = selected
            self.rebuild_matrix()
            dialog.destroy()

        buttons = ttk.Frame(dialog, padding=8)
        buttons.pack(fill="x", side="bottom")
        ttk.Button(buttons, text="Set current layout as default", command=lambda: (apply(), self.save_current_layout())).pack(side="left")
        ttk.Button(buttons, text="Apply", command=apply).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(0, 6))

    def _schedule_refresh(self) -> None:
        if self.auto_refresh_var.get():
            self.refresh_matrix()
        interval = max(5, int(self.refresh_interval_var.get())) * 1000
        self.root.after(interval, self._schedule_refresh)

    def close(self) -> None:
        for tab in list(self.tail_tabs.values()):
            tab.stop()
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--dataflow-root", default=DEFAULT_DATAFLOW_ROOT)
    parser.add_argument("--cron-log-root", default=DEFAULT_CRON_LOG_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--lines", type=int, default=None)
    parser.add_argument("--refresh-interval", type=int, default=None)
    parser.add_argument("--include-inactive", action="store_true")
    parser.add_argument("--no-auto-refresh", action="store_true")
    parser.add_argument("--reset-layout", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = tk.Tk()
    CronLogMatrixApp(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
