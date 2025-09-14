# 项目地址：https://github.com/yutto-dev/yutto
# 项目文档：https://yutto.nyakku.moe/
# 打包命令：pyinstaller --onedir --windowed bilibiliDownloader_dev.py 

import os
import sys
import subprocess
import threading
import customtkinter as ctk
from tkinter import filedialog
import queue
import shlex
import re

# Windows 下不弹出命令行窗口
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

# ---------------- 打包友好 ----------------
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

YUTTO_CMD = os.path.join(ROOT_DIR, "yutto.exe")
FFMPEG_CMD = os.path.join(ROOT_DIR, "ffmpeg.exe")  # 如果 yutto 需要 ffmpeg

# 初始化 CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class YuttoGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("yutto GUI — B站下载器（非遗社区：www.chinarts.org）")
        self.geometry("1000x700")
        self.minsize(900, 600)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.process = None
        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        self.selected_stream = None

        # 顶部导航栏
        self._create_menu()
        # 界面控件
        self._create_widgets()
        # grid 布局
        self._setup_grid()
        # 日志队列轮询
        self.after(100, self._poll_log_queue)

    # ---------------- 菜单 ----------------
    def _create_menu(self):
        self.navbar = ctk.CTkFrame(self, fg_color="#2a2a2a", height=35)
        self.navbar.grid(row=0, column=0, sticky="ew")
        self.navbar.grid_propagate(False)

        btn_about = ctk.CTkButton(
            self.navbar,
            text="关于软件",
            fg_color="#2a2a2a",
            hover_color="#1c1c1c",
            text_color="#ffffff",
            command=self.show_about
        )
        btn_about.pack(side="left", padx=5, pady=2)

    # ---------------- Grid 布局 ----------------
    def _setup_grid(self):
        self.rowconfigure(0, weight=0)  # navbar
        self.rowconfigure(1, weight=0)  # top_frame
        self.rowconfigure(2, weight=1)  # middle_frame
        self.rowconfigure(3, weight=0)  # bottom_frame
        self.rowconfigure(4, weight=2)  # log_text
        self.columnconfigure(0, weight=1)
        self.top_frame.columnconfigure(1, weight=1)

    # ---------------- 关于软件弹窗 ----------------
    def show_about(self):
        about_win = ctk.CTkToplevel(self)
        about_win.withdraw()
        about_win.title("关于软件")
        about_win.geometry("300x150")
        about_win.resizable(False, False)
        about_win.configure(fg_color=ctk.ThemeManager.theme["CTkToplevel"]["fg_color"])

        frame = ctk.CTkFrame(about_win, fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        frame.pack(expand=True, fill="both", padx=10, pady=10)

        ctk.CTkLabel(
            frame,
            text="这是一个免费的软件，在yutto\n开源项目的基础上编写的可视化程序。\n了解更多请在github上搜索项目文档\n进行查看。",
            font=("Arial", 14),
            text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        ).pack(expand=True)

        btn_close = ctk.CTkButton(frame, text="关闭", command=about_win.destroy)
        btn_close.pack(pady=10)
        btn_close.configure(
            fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
            hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],
            text_color=ctk.ThemeManager.theme["CTkButton"]["text_color"]
        )

        # 居中显示
        self.update_idletasks()
        self_center_x = self.winfo_x() + self.winfo_width() // 2
        self_center_y = self.winfo_y() + self.winfo_height() // 2
        win_width, win_height = 300, 150
        x = self_center_x - win_width // 2
        y = self_center_y - win_height // 2
        about_win.geometry(f"{win_width}x{win_height}+{x}+{y}")

        about_win.deiconify()
        about_win.transient(self)
        about_win.grab_set()
        about_win.focus()

    # ---------------- 界面控件 ----------------
    def _create_widgets(self):
        # top_frame
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        ctk.CTkLabel(self.top_frame, text="视频/系列 URL:").grid(row=0, column=0, sticky="w", pady=3)
        self.entry_url = ctk.CTkEntry(self.top_frame, placeholder_text="请输入视频/系列 URL",
                                      height=30, fg_color="#2a2a2a", text_color="#ffffff")
        self.entry_url.grid(row=0, column=1, sticky="ew", padx=5)
        self.btn_parse = ctk.CTkButton(self.top_frame, text="解析", width=80, command=self.parse_streams)
        self.btn_parse.grid(row=0, column=2, padx=5)

        ctk.CTkLabel(self.top_frame, text="输出目录:").grid(row=1, column=0, sticky="w", pady=3)
        self.entry_out = ctk.CTkEntry(self.top_frame, height=30, fg_color="#2a2a2a", text_color="#ffffff")
        self.entry_out.insert(0, os.getcwd())
        self.entry_out.grid(row=1, column=1, sticky="ew", padx=5)
        self.btn_folder = ctk.CTkButton(self.top_frame, text="选择", width=80, command=self.select_folder)
        self.btn_folder.grid(row=1, column=2, padx=5)

        self.var_batch = ctk.BooleanVar()
        self.var_vip = ctk.BooleanVar()
        self.chk_batch = ctk.CTkCheckBox(self.top_frame, text="批量模式 (--batch)", variable=self.var_batch,
                                         onvalue=True, offvalue=False, checkmark_color="#00aaff")
        self.chk_batch.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.chk_vip = ctk.CTkCheckBox(self.top_frame, text="大会员", variable=self.var_vip,
                                       onvalue=True, offvalue=False, checkmark_color="#00aaff")
        self.chk_vip.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(self.top_frame, text="额外参数:").grid(row=3, column=0, sticky="w", pady=3)
        self.entry_extra = ctk.CTkEntry(self.top_frame, height=30, fg_color="#2a2a2a", text_color="#ffffff")
        self.entry_extra.grid(row=3, column=1, sticky="ew", padx=5)

        # middle_frame
        self.middle_frame = ctk.CTkFrame(self)
        self.middle_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        ctk.CTkLabel(self.middle_frame, text="可用流/画质:").pack(anchor="w", pady=3)
        self.list_streams = ctk.CTkTextbox(self.middle_frame, height=100,
                                           fg_color="#2a2a2a", text_color="#ffffff",
                                           state="disabled")
        self.list_streams.pack(fill="both", expand=True, padx=5, pady=5)
        self.list_streams.bind("<1>", lambda event: self._select_stream(event))

        # bottom_frame
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        self.btn_dl = ctk.CTkButton(self.bottom_frame, text="下载", width=100, command=self.start_download)
        self.btn_dl.pack(side="left", padx=5)
        self.btn_cancel = ctk.CTkButton(self.bottom_frame, text="取消", width=100, command=self.cancel_download,
                                        state="disabled")
        self.btn_cancel.pack(side="left", padx=5)

        # log_text
        self.log_text = ctk.CTkTextbox(self, height=250,
                                       fg_color="#2a2a2a", text_color="#ffffff",
                                       state="disabled")
        self.log_text.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)

    # ---------------- 功能方法 ----------------
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_out.delete(0, ctk.END)
            self.entry_out.insert(0, folder)

    def append_log(self, msg, color=None):
        self.log_queue.put(("log", msg, color))

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item[0] == "log":
                    _, text, color = item
                    self.log_text.configure(state="normal")
                    self.log_text.insert(ctk.END, text)
                    self.log_text.see(ctk.END)
                    self.log_text.configure(state="disabled")
                elif item[0] == "streams":
                    _, streams = item
                    self.list_streams.configure(state="normal")
                    self.list_streams.delete("0.0", ctk.END)
                    for s in streams:
                        self.list_streams.insert(ctk.END, f"{s}\n")
                    self.list_streams.configure(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_log_queue)

    # ---------------- 解析 ----------------
    def parse_streams(self):
        url = self.entry_url.get().strip()
        if not url:
            self.append_log("请输入 URL!\n", color="red")
            return
        self.append_log(f"开始解析 {url}...\n")
        threading.Thread(target=self._parse_worker, args=(url,), daemon=True).start()

    def _parse_worker(self, url):
        candidate = [["-j", url], ["--json", url]]
        streams = []
        for cand in candidate:
            try:
                cmd = [YUTTO_CMD] + cand
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=CREATE_NO_WINDOW)
                try:
                    out, _ = p.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    out = p.stdout.read() if p.stdout else ""
                for line in (out or "").splitlines():
                    match = re.search(r'\d+p', line)
                    if match:
                        t = line.strip()
                        if t not in streams:
                            streams.append(t)
                if streams:
                    break
            except Exception:
                continue
        if not streams:
            streams = ["默认（自动）"]
        self.log_queue.put(("streams", streams))
        self.append_log("解析完成。\n", color="green")

    def _select_stream(self, event):
        index = self.list_streams.index(f"@{event.y},{event.x}")
        line = self.list_streams.get(index + " linestart", index + " lineend").strip()
        self.selected_stream = line

    # ---------------- 下载 ----------------
    def start_download(self):
        url = self.entry_url.get().strip()
        if not url:
            self.append_log("请输入 URL!\n", color="red")
            return

        out_dir = self.entry_out.get().strip() or os.getcwd()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            self.append_log(f"无法创建目录: {out_dir}\n", color="red")
            return

        extra = self.entry_extra.get().strip()
        args = []

        if self.var_batch.get():
            args.append("--batch")
        if self.var_vip.get():
            args.append("--vip")
        if extra:
            args += shlex.split(extra)
        if self.selected_stream and self.selected_stream != "默认（自动）":
            args += ["--format", self.selected_stream]

        # 正确输出目录参数
        args += ["-d", out_dir]  # yutto 使用 -d 指定输出目录
        args.append(url)          # URL 单独放最后

        self.btn_dl.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.stop_event.clear()

        self.log_text.configure(state="normal")
        self.log_text.delete("0.0", ctk.END)
        self.log_text.configure(state="disabled")

        # 启动下载线程
        threading.Thread(target=self._download_worker, args=(args,), daemon=True).start()


    def _download_worker(self, args):
        self.run_yutto_command(args)


    def run_yutto_command(self, args):
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            self.process = subprocess.Popen([YUTTO_CMD] + args,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            text=True,
                                            encoding="utf-8",
                                            errors="replace",
                                            bufsize=1,
                                            env=env,
                                            creationflags=CREATE_NO_WINDOW)
        except FileNotFoundError:
            self.append_log(f"错误：未找到命令 {YUTTO_CMD}\n", color="red")
            self.btn_dl.configure(state="normal")
            self.btn_cancel.configure(state="disabled")
            return

        for line in self.process.stdout:
            line = line.rstrip()
            if line:
                self.append_log(line + "\n")

        try:
            rc = self.process.wait()
        except Exception:
            rc = -1
        self.btn_dl.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.process = None
        self.append_log(f"任务结束，返回码 {rc}\n", color="green")

    def cancel_download(self):
        self.stop_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.append_log("已取消下载\n", color="red")
        self.btn_cancel.configure(state="disabled")
        self.btn_dl.configure(state="normal")

    def on_close(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = YuttoGUI()
    app.mainloop()
