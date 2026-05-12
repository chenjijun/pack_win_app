import sys
import os
import time
import threading
import datetime
import requests
from tkinter import (
    Tk, Frame, Label, Entry, Spinbox, Button, Text,
    Scrollbar, StringVar, IntVar, messagebox, filedialog
)
from tkinter.ttk import Progressbar, Style
import encodings



class DialTestTool:
    def __init__(self, root):
        self.root = root
        self.root.title("接口拨测工具")
        self.root.geometry("1000x700")

        # 控制标志
        self.is_running = False
        self.is_paused = False
        self.start_time = None

        # 日志存储
        self.logs = []

        self.create_widgets()
        self.setup_style()

    def setup_style(self):
        style = Style()
        style.theme_use('vista')  # 或 'clam', 'alt' 等，避免 win10 默认样式 bug

    def create_widgets(self):
        main_frame = Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # === 配置区 ===
        config_frame = Frame(main_frame)
        config_frame.pack(fill="x", pady=5)

        Label(config_frame, text="目标URL:").grid(row=0, column=0, sticky="w")
        self.url_var = StringVar(value="https://www.baidu.com")
        url_entry = Entry(config_frame, textvariable=self.url_var, width=80)
        url_entry.grid(row=0, column=1, columnspan=5, sticky="ew", padx=(5, 0))

        Label(config_frame, text="拨测次数:").grid(row=1, column=0, sticky="w", pady=5)
        self.count_var = IntVar(value=1000)
        count_spin = Spinbox(config_frame, from_=1, to=100000, textvariable=self.count_var, width=10)
        count_spin.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=5)

        Label(config_frame, text="并发数:").grid(row=1, column=2, sticky="w", pady=5)
        self.concurrency_var = IntVar(value=50)
        concurrency_spin = Spinbox(config_frame, from_=1, to=500, textvariable=self.concurrency_var, width=10)
        concurrency_spin.grid(row=1, column=3, sticky="w", padx=(5, 0), pady=5)

        Label(config_frame, text="超时秒数:").grid(row=1, column=4, sticky="w", pady=5)
        self.timeout_var = IntVar(value=5)
        timeout_spin = Spinbox(config_frame, from_=1, to=300, textvariable=self.timeout_var, width=10)
        timeout_spin.grid(row=1, column=5, sticky="w", padx=(5, 0), pady=5)

        config_frame.columnconfigure(1, weight=1)

        # === 控制按钮 ===
        btn_frame = Frame(main_frame)
        btn_frame.pack(fill="x", pady=5)

        self.start_btn = Button(btn_frame, text="开始拨测", bg="#28a745", fg="white", command=self.start_test)
        self.pause_btn = Button(btn_frame, text="暂停", state="disabled", command=self.pause_test)
        self.resume_btn = Button(btn_frame, text="继续", state="disabled", command=self.resume_test)
        self.stop_btn = Button(btn_frame, text="结束", bg="#dc3545", fg="white", state="disabled", command=self.stop_test)
        self.reset_btn = Button(btn_frame, text="重置", bg="#007bff", fg="white", command=self.reset_test)
        self.export_btn = Button(btn_frame, text="导出日志", bg="#17a2b8", fg="white", command=self.export_log)

        for btn in [self.start_btn, self.pause_btn, self.resume_btn, self.stop_btn, self.reset_btn, self.export_btn]:
            btn.pack(side="left", padx=5, ipadx=10)

        # === 统计信息 ===
        stats_frame = Frame(main_frame)
        stats_frame.pack(fill="x", pady=5)

        self.stats_var = StringVar(value="总次数:0  成功:0  失败:0  成功率:0.0%")
        Label(stats_frame, textvariable=self.stats_var).pack(anchor="w")

        self.time_var = StringVar(value="开始:--  结束:--  耗时:--")
        Label(stats_frame, textvariable=self.time_var).pack(anchor="w")

        # === 进度条 ===
        progress_frame = Frame(main_frame)
        progress_frame.pack(fill="x", pady=5)

        self.progress_bar = Progressbar(progress_frame, orient="horizontal", length=800, mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True)

        self.progress_text = StringVar(value="0/0 (0.0%)")
        Label(progress_frame, textvariable=self.progress_text, width=15).pack(side="right", padx=(10, 0))

        # === 日志区 ===
        log_frame = Frame(main_frame)
        log_frame.pack(fill="both", expand=True, pady=5)

        self.log_text = Text(log_frame, wrap="word", bg="#222", fg="#eee", font=("Consolas", 10))
        scrollbar = Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ====== 功能逻辑 ======
    def do_request(self, url, timeout):
        try:
            resp = requests.get(url, timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def run_test(self):
        url = self.url_var.get().strip()
        total = self.count_var.get()
        concurrency = self.concurrency_var.get()
        timeout = self.timeout_var.get()

        if not url:
            self.root.after(0, lambda: messagebox.showwarning("警告", "请输入URL"))
            return

        # 初始化状态
        self.success = 0
        self.fail = 0
        self.completed = 0
        self.total = total
        self.start_time = datetime.datetime.now()

        self.log(f"目标URL: {url}")
        self.log(f"总拨测次数: {total}")
        self.log(f"并发数: {concurrency}")
        self.log(f"超时时间: {timeout}秒")
        self.log(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("-" * 50)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for i in range(total):
                if not self.is_running:
                    break

                while self.is_paused and self.is_running:
                    time.sleep(0.1)

                futures.append(executor.submit(self.do_request, url, timeout))

                if len(futures) >= concurrency or i == total - 1:
                    for future in as_completed(futures):
                        if not self.is_running:
                            break
                        self.completed += 1
                        ok = future.result()
                        if ok:
                            self.success += 1
                        else:
                            self.fail += 1

                        # 安全更新 UI
                        progress = int(self.completed / total * 100)
                        rate = self.success / self.completed * 100 if self.completed else 0
                        self.root.after(0, self.update_ui, progress, rate)

                    futures.clear()

        # 测试结束
        end_time = datetime.datetime.now()
        cost = (end_time - self.start_time).total_seconds()
        minutes, seconds = divmod(int(cost), 60)

        self.log("-" * 50)
        self.log(f"实际完成: {self.completed} | 成功: {self.success} | 失败: {self.fail}")
        if self.completed > 0:
            final_rate = self.success / self.completed * 100
            self.log(f"成功率: {final_rate:.2f}%")
        self.log(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        self.root.after(0, self.test_finished, end_time, minutes, seconds)

    def update_ui(self, progress, rate):
        self.progress_bar["value"] = progress
        done = int(progress * self.total / 100)
        self.progress_text.set(f"{done}/{self.total} ({progress}%)")
        self.stats_var.set(f"总次数:{self.total}  成功:{self.success}  失败:{self.fail}  成功率:{rate:.2f}%")

    def test_finished(self, end_time, minutes, seconds):
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.reset_btn.config(state="normal")

        self.time_var.set(
            f"开始:{self.start_time.strftime('%H:%M:%S')}  "
            f"结束:{end_time.strftime('%H:%M:%S')}  "
            f"耗时:{minutes}:{seconds:02d}"
        )

    def start_test(self):
        self.is_running = True
        self.is_paused = False
        threading.Thread(target=self.run_test, daemon=True).start()

        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        self.reset_btn.config(state="disabled")

    def pause_test(self):
        self.is_paused = True
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="normal")
        self.log("【已暂停拨测】")

    def resume_test(self):
        self.is_paused = False
        self.pause_btn.config(state="normal")
        self.resume_btn.config(state="disabled")
        self.log("【继续拨测】")

    def stop_test(self):
        self.is_running = False
        self.log("【正在终止拨测...】")

    def reset_test(self):
        self.progress_bar["value"] = 0
        self.progress_text.set("0/0 (0.0%)")
        self.stats_var.set("总次数:0  成功:0  失败:0  成功率:0.0%")
        self.time_var.set("开始:--  结束:--  耗时:--")
        self.log_text.delete("1.0", "end")
        self.logs = []

    def log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.logs.append(msg)

    def export_log(self):
        if not self.logs:
            messagebox.showwarning("提示", "无日志可导出")
            return
        path = filedialog.asksaveasfilename(
            title="导出日志",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("CSV 文件", "*.csv")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.logs))
            messagebox.showinfo("成功", "日志导出完成")


if __name__ == "__main__":
    # 解决 Windows 控制台编码问题（不影响 GUI）
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    root = Tk()
    app = DialTestTool(root)
    root.mainloop()