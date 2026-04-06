import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from tiktok_downloader import TikTokDownloadError, TikTokDownloader


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TikTok 无水印下载器")
        self.root.geometry("640x280")

        self.downloader = TikTokDownloader()

        self.url_var = tk.StringVar()
        self.dir_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.status_var = tk.StringVar(value="准备就绪")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="TikTok 视频链接").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.url_var, width=72).grid(row=1, column=0, columnspan=2, pady=(4, 12), sticky="we")

        tk.Label(frame, text="保存目录").grid(row=2, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.dir_var, width=56).grid(row=3, column=0, pady=(4, 12), sticky="we")
        tk.Button(frame, text="浏览...", command=self._choose_dir).grid(row=3, column=1, padx=(8, 0), sticky="e")

        tk.Button(frame, text="开始下载", command=self._start_download, height=2).grid(row=4, column=0, columnspan=2, sticky="we")

        tk.Label(frame, textvariable=self.status_var, fg="#555").grid(row=5, column=0, columnspan=2, pady=(14, 0), sticky="w")

        frame.columnconfigure(0, weight=1)

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.home()))
        if chosen:
            self.dir_var.set(chosen)

    def _start_download(self) -> None:
        url = self.url_var.get().strip()
        output_dir = self.dir_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先输入 TikTok 视频链接。")
            return
        if not output_dir:
            messagebox.showwarning("提示", "请先选择保存目录。")
            return

        self.status_var.set("正在解析并下载，请稍候...")
        threading.Thread(target=self._download_task, args=(url, output_dir), daemon=True).start()

    def _download_task(self, url: str, output_dir: str) -> None:
        try:
            info = self.downloader.get_video_info(url)
            file_path = self.downloader.download(info, output_dir)
            self.root.after(0, lambda: self._on_success(file_path))
        except TikTokDownloadError as exc:
            self.root.after(0, lambda: self._on_error(str(exc)))
        except Exception as exc:  # 保底异常
            self.root.after(0, lambda: self._on_error(f"未知错误：{exc}"))

    def _on_success(self, file_path: Path) -> None:
        self.status_var.set(f"下载完成：{file_path}")
        messagebox.showinfo("成功", f"视频已下载到：\n{file_path}")

    def _on_error(self, error_msg: str) -> None:
        self.status_var.set("下载失败")
        messagebox.showerror("错误", error_msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
