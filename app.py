import queue
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from stabilizer import StabilizeConfig, StabilizeError, choose_manual_roi, gpu_available, stabilize_video


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PR 跟踪稳定软件（AI + GPU）")
        self.root.geometry("980x660")

        self.selected_videos: list[str] = []
        self.manual_rois: dict[str, tuple[int, int, int, int]] = {}
        self.task_rows: dict[str, str] = {}
        self.event_queue: queue.Queue[tuple] = queue.Queue()
        self.running = False

        self.output_var = tk.StringVar(value=str(Path.home() / "Videos" / "Stabilized"))
        self.status_var = tk.StringVar(value="准备就绪")
        self.global_progress_var = tk.DoubleVar(value=0)

        self.auto_detect_var = tk.BooleanVar(value=True)
        self.gpu_var = tk.BooleanVar(value=gpu_available())
        self.black_border_var = tk.BooleanVar(value=True)
        self.preview_var = tk.BooleanVar(value=False)
        self.workers_var = tk.IntVar(value=2)
        self.smooth_var = tk.DoubleVar(value=0.85)

        self._build_ui()
        self.root.after(120, self._pump_events)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=14)
        shell.pack(fill="both", expand=True)

        cfg = ttk.LabelFrame(shell, text="任务配置", padding=12)
        cfg.pack(fill="x")

        ttk.Button(cfg, text="选择视频（可多选）", command=self._choose_videos).grid(row=0, column=0, sticky="w")
        ttk.Button(cfg, text="手动选跟踪部位", command=self._choose_manual_roi).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Button(cfg, text="清空手动选区", command=self._clear_manual_roi).grid(row=0, column=2, sticky="w")

        ttk.Label(cfg, text="输出目录").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(cfg, textvariable=self.output_var, width=78).grid(row=2, column=0, columnspan=3, sticky="we", pady=(2, 0))
        ttk.Button(cfg, text="浏览", command=self._choose_output_dir).grid(row=2, column=3, sticky="e", padx=(8, 0))

        opts = ttk.Frame(cfg)
        opts.grid(row=3, column=0, columnspan=4, sticky="we", pady=(10, 0))
        ttk.Checkbutton(opts, text="AI 自动识别目标", variable=self.auto_detect_var).pack(side="left")
        ttk.Checkbutton(opts, text="GPU 加速", variable=self.gpu_var).pack(side="left", padx=12)
        ttk.Checkbutton(opts, text="防黑边处理", variable=self.black_border_var).pack(side="left")
        ttk.Checkbutton(opts, text="实时预览", variable=self.preview_var).pack(side="left", padx=12)

        tune = ttk.Frame(cfg)
        tune.grid(row=4, column=0, columnspan=4, sticky="we", pady=(10, 0))
        ttk.Label(tune, text="平滑强度").pack(side="left")
        ttk.Scale(tune, from_=0.05, to=0.98, variable=self.smooth_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Label(tune, text="并发任务").pack(side="left", padx=(10, 6))
        ttk.Spinbox(tune, from_=1, to=8, textvariable=self.workers_var, width=4).pack(side="left")

        actions = ttk.Frame(cfg)
        actions.grid(row=5, column=0, columnspan=4, sticky="we", pady=(12, 0))
        ttk.Button(actions, text="开始批处理", command=self._start).pack(side="left")
        ttk.Label(actions, textvariable=self.status_var).pack(side="left", padx=12)

        list_box = ttk.LabelFrame(shell, text="任务状态（多任务）", padding=10)
        list_box.pack(fill="both", expand=True, pady=(14, 0))

        cols = ("file", "progress", "status")
        self.tree = ttk.Treeview(list_box, columns=cols, show="headings", height=16)
        self.tree.heading("file", text="视频")
        self.tree.heading("progress", text="进度%")
        self.tree.heading("status", text="任务状态")
        self.tree.column("file", width=520)
        self.tree.column("progress", width=100, anchor="center")
        self.tree.column("status", width=220, anchor="center")
        self.tree.pack(fill="both", expand=True)

        ttk.Progressbar(shell, variable=self.global_progress_var, maximum=100).pack(fill="x", pady=(10, 0))

        cfg.columnconfigure(0, weight=1)

    def _choose_videos(self) -> None:
        files = filedialog.askopenfilenames(
            title="选择要稳定的视频",
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.m4v"), ("All", "*.*")],
        )
        if not files:
            return

        self.selected_videos = list(files)
        self.tree.delete(*self.tree.get_children())
        self.task_rows.clear()
        for file_path in self.selected_videos:
            item = self.tree.insert("", "end", values=(Path(file_path).name, "0", "已加入队列"))
            self.task_rows[file_path] = item
        self.status_var.set(f"已选择 {len(self.selected_videos)} 个视频")

    def _choose_manual_roi(self) -> None:
        if not self.selected_videos:
            messagebox.showwarning("提示", "请先选择视频。")
            return

        video = self.selected_videos[0]
        self.status_var.set("正在打开手动选区窗口...")
        roi = choose_manual_roi(video)
        if not roi:
            self.status_var.set("未设置手动选区")
            return

        for v in self.selected_videos:
            self.manual_rois[v] = roi
        self.status_var.set(f"已设置手动跟踪区域：{roi}")

    def _clear_manual_roi(self) -> None:
        self.manual_rois.clear()
        self.status_var.set("已清空手动选区")

    def _choose_output_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.home()))
        if chosen:
            self.output_var.set(chosen)

    def _start(self) -> None:
        if self.running:
            messagebox.showinfo("提示", "任务正在处理，请稍候。")
            return
        if not self.selected_videos:
            messagebox.showwarning("提示", "请先选择要处理的视频。")
            return

        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showwarning("提示", "请先选择输出目录。")
            return

        self.running = True
        self.global_progress_var.set(0)
        self.status_var.set("任务开始执行...")

        threading.Thread(target=self._run_tasks, daemon=True).start()

    def _run_tasks(self) -> None:
        worker_count = max(1, int(self.workers_var.get()))
        all_tasks = len(self.selected_videos)

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = []
            for video_path in self.selected_videos:
                futures.append(executor.submit(self._run_single, video_path))

            done = 0
            for fut in futures:
                fut.result()
                done += 1
                self.event_queue.put(("global", done / all_tasks * 100.0))

        self.event_queue.put(("done",))

    def _run_single(self, video_path: str) -> None:
        in_path = Path(video_path)
        out_path = Path(self.output_var.get()) / f"{in_path.stem}_stabilized.mp4"

        config = StabilizeConfig(
            use_gpu=self.gpu_var.get(),
            anti_black_border=self.black_border_var.get(),
            auto_detect=self.auto_detect_var.get(),
            smoothing_alpha=float(self.smooth_var.get()),
            preview=self.preview_var.get(),
        )

        if config.use_gpu and not gpu_available():
            self.event_queue.put(("status", video_path, "GPU 不可用，已回退 CPU"))
            config.use_gpu = False

        self.event_queue.put(("status", video_path, "处理中"))

        def on_progress(current: int, total: int, stage: str) -> None:
            ratio = 0.0 if total <= 0 else min(100.0, current / total * 100.0)
            self.event_queue.put(("progress", video_path, ratio, stage))

        try:
            stabilize_video(
                input_path=str(in_path),
                output_path=str(out_path),
                config=config,
                progress_cb=on_progress,
                manual_roi=self.manual_rois.get(video_path),
            )
            self.event_queue.put(("status", video_path, f"完成 -> {out_path.name}"))
        except StabilizeError as exc:
            self.event_queue.put(("status", video_path, f"失败：{exc}"))
        except Exception as exc:
            self.event_queue.put(("status", video_path, f"异常：{exc}"))

    def _pump_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break

            etype = event[0]
            if etype == "progress":
                _, video_path, progress, stage = event
                row = self.task_rows.get(video_path)
                if row:
                    name = Path(video_path).name
                    self.tree.item(row, values=(name, f"{progress:.1f}", stage))
            elif etype == "status":
                _, video_path, status = event
                row = self.task_rows.get(video_path)
                if row:
                    values = self.tree.item(row, "values")
                    progress = values[1] if len(values) > 1 else "0"
                    self.tree.item(row, values=(Path(video_path).name, progress, status))
                self.status_var.set(status)
            elif etype == "global":
                _, value = event
                self.global_progress_var.set(value)
            elif etype == "done":
                self.running = False
                self.status_var.set("全部任务完成")
                messagebox.showinfo("完成", "所有视频处理完成。")

        self.root.after(120, self._pump_events)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
