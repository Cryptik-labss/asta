from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, ttk

from app.identify.tle import load_tle_file
from app.output.writer import flush_batch_results, init_output_store, write_result
from app.pipeline.processor import process_frame
from app.pipeline.types import Frame
from config import Config


def _collect_input_files(source_path: str) -> list[Path]:
    root = Path(source_path)
    files: list[Path] = []
    for ext in ("*.fits", "*.fit", "*.fts", "*.png", "*.jpg", "*.jpeg"):
        files.extend(root.rglob(ext))
    return sorted(set(files))


def _frame_from_file(file_path: Path) -> Frame:
    suffix = file_path.suffix.lower()
    fmt = "fits" if suffix in {".fits", ".fit", ".fts"} else "png"
    return Frame(
        id=file_path.stem,
        file_path=str(file_path),
        format=fmt,
        timestamp_utc=datetime.now(timezone.utc),
        source="directory",
    )


class ASTAGUI:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.root = tk.Tk()
        self.root.title("ASTA GUI")
        self.root.geometry("920x620")

        self.input_dir = tk.StringVar(value=cfg.source_path)
        self.output_dir = tk.StringVar(value=cfg.output_dir)
        self.host = tk.StringVar(value="0.0.0.0")
        self.port = tk.StringVar(value="8000")
        self.progress = tk.StringVar(value="idle")

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._batch_thread: threading.Thread | None = None
        self._batch_cancel = threading.Event()
        self._realtime_proc: subprocess.Popen | None = None

        self._build_layout()
        self._tick_logs()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(frame, text="ASTA Desktop Control", font=("TkDefaultFont", 13, "bold"))
        title.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 10))

        ttk.Label(frame, text="Input dir").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.input_dir, width=72).grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse", command=self._pick_input).grid(row=1, column=4, padx=(8, 0))

        ttk.Label(frame, text="Output dir").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.output_dir, width=72).grid(row=2, column=1, columnspan=3, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse", command=self._pick_output).grid(row=2, column=4, padx=(8, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=5, sticky="ew", pady=10)

        batch_label = ttk.Label(frame, text="Batch mode", font=("TkDefaultFont", 10, "bold"))
        batch_label.grid(row=4, column=0, sticky="w")
        ttk.Button(frame, text="Run batch", command=self._start_batch).grid(row=4, column=1, sticky="w")
        ttk.Button(frame, text="Stop batch", command=self._stop_batch).grid(row=4, column=2, sticky="w", padx=(6, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=5, column=0, columnspan=5, sticky="ew", pady=10)

        rt_label = ttk.Label(frame, text="Realtime API", font=("TkDefaultFont", 10, "bold"))
        rt_label.grid(row=6, column=0, sticky="w")
        ttk.Label(frame, text="Host").grid(row=6, column=1, sticky="e")
        ttk.Entry(frame, textvariable=self.host, width=14).grid(row=6, column=2, sticky="w")
        ttk.Label(frame, text="Port").grid(row=6, column=3, sticky="e")
        ttk.Entry(frame, textvariable=self.port, width=10).grid(row=6, column=4, sticky="w")
        ttk.Button(frame, text="Start API", command=self._start_realtime).grid(row=7, column=1, sticky="w", pady=(6, 0))
        ttk.Button(frame, text="Stop API", command=self._stop_realtime).grid(row=7, column=2, sticky="w", padx=(6, 0), pady=(6, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=8, column=0, columnspan=5, sticky="ew", pady=10)
        ttk.Label(frame, text="Status").grid(row=9, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.progress).grid(row=9, column=1, columnspan=4, sticky="w")

        ttk.Label(frame, text="Log").grid(row=10, column=0, sticky="w", pady=(8, 4))
        self.log = tk.Text(frame, height=22, wrap=tk.WORD, state=tk.DISABLED)
        self.log.grid(row=11, column=0, columnspan=5, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log.yview)
        scroll.grid(row=11, column=4, sticky="nse")
        self.log.configure(yscrollcommand=scroll.set)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(11, weight=1)

    def _pick_input(self) -> None:
        path = filedialog.askdirectory(initialdir=self.input_dir.get() or os.getcwd())
        if path:
            self.input_dir.set(path)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(initialdir=self.output_dir.get() or os.getcwd())
        if path:
            self.output_dir.set(path)

    def _append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{text}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _tick_logs(self) -> None:
        try:
            while True:
                self._append_log(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self._tick_logs)

    def _start_batch(self) -> None:
        if self._batch_thread and self._batch_thread.is_alive():
            self._log_queue.put("batch already running")
            return
        self._batch_cancel.clear()
        self.progress.set("batch running")
        self._batch_thread = threading.Thread(target=self._run_batch_worker, daemon=True)
        self._batch_thread.start()

    def _stop_batch(self) -> None:
        if self._batch_thread and self._batch_thread.is_alive():
            self._batch_cancel.set()
            self._log_queue.put("requested batch stop")
        else:
            self._log_queue.put("batch not running")

    def _run_batch_worker(self) -> None:
        try:
            cfg = Config(**self.cfg.to_dict())
            cfg.source_path = self.input_dir.get().strip() or cfg.source_path
            cfg.output_dir = self.output_dir.get().strip() or cfg.output_dir

            tles = load_tle_file(cfg.tle_active_path)
            if cfg.tle_historical_path:
                tles.extend(load_tle_file(cfg.tle_historical_path))
            self._log_queue.put(f"loaded {len(tles)} tle records")

            files = _collect_input_files(cfg.source_path)
            self._log_queue.put(f"found {len(files)} input files")
            init_output_store(cfg.output_dir)

            if not files:
                flush_batch_results(cfg.output_dir)
                self._log_queue.put("no frames found batch finished")
                self.progress.set("batch done")
                return

            for idx, path in enumerate(files, start=1):
                if self._batch_cancel.is_set():
                    self._log_queue.put("batch cancelled by user")
                    break
                frame = _frame_from_file(path)
                try:
                    result = process_frame(frame, cfg, tles=tles)
                    write_result(result, cfg)
                    self._log_queue.put(
                        f"[{idx}/{len(files)}] {frame.id} status={result.status} trails={len(result.trails)}"
                    )
                except Exception as exc:  # noqa: BLE001
                    self._log_queue.put(f"[{idx}/{len(files)}] {frame.id} failed {exc}")
            flush_batch_results(cfg.output_dir)
            self.progress.set("batch done")
            self._log_queue.put("batch complete")
        except Exception:  # noqa: BLE001
            self.progress.set("batch failed")
            self._log_queue.put("batch failed with exception")
            self._log_queue.put(traceback.format_exc())

    def _start_realtime(self) -> None:
        if self._realtime_proc and self._realtime_proc.poll() is None:
            self._log_queue.put("realtime api already running")
            return
        host = self.host.get().strip() or "0.0.0.0"
        port = self.port.get().strip() or "8000"
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:create_uvicorn_app",
            "--factory",
            "--host",
            host,
            "--port",
            port,
        ]
        self._realtime_proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[2]))
        self.progress.set("realtime api running")
        self._log_queue.put(f"realtime api started on {host}:{port}")

    def _stop_realtime(self) -> None:
        if self._realtime_proc and self._realtime_proc.poll() is None:
            self._realtime_proc.terminate()
            self._realtime_proc.wait(timeout=5)
            self._log_queue.put("realtime api stopped")
            self.progress.set("idle")
        else:
            self._log_queue.put("realtime api not running")

    def _on_close(self) -> None:
        self._stop_batch()
        try:
            self._stop_realtime()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui(cfg: Config) -> None:
    app = ASTAGUI(cfg)
    app.run()
