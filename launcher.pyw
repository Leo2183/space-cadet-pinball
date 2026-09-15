# -*- coding: utf-8 -*-
"""三维弹球: 太空军校生 —— 图形启动器(仅标准库, 不依赖 Ursina)

双击本文件即可打开启动器; 命令行模式:
    python launcher.pyw --check    检查解释器/依赖/最高分(无界面)
    python launcher.pyw --launch   找到可用解释器后直接启动游戏
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
TESTS = os.path.join(HERE, "tests", "test_physics.py")
REQS = os.path.join(HERE, "requirements.txt")
HI_FILE = os.path.join(HERE, "highscore.json")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
FONT = ("Microsoft YaHei UI", 10)
FONT_TITLE = ("Microsoft YaHei UI", 16, "bold")


# ---------------------------------------------------------------- 解释器探测
def candidate_pythons():
    """按优先级收集本机候选 Python(文件路径或 'py' 这类裸命令)。"""
    out = []

    def add(p):
        if p and p not in out:
            out.append(p)

    add(sys.executable)
    add(r"C:\ProgramData\anaconda3\python.exe")
    add(os.path.expanduser(r"~\anaconda3\python.exe"))
    add(os.path.expanduser(r"~\miniconda3\python.exe"))
    for p in glob.glob(r"C:\ProgramData\anaconda3\envs\*\python.exe"):
        add(p)
    for name in ("python", "python3", "py"):
        add(shutil.which(name))
    return [p for p in out
            if os.path.isfile(p) or (os.path.sep not in p and "/" not in p)]


def probe(py, code, timeout=20):
    try:
        r = subprocess.run([py, "-c", code], capture_output=True,
                           timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def has_ursina(py):
    return probe(py, "import ursina")


def find_python():
    """返回第一个装了 Ursina 的解释器; 没有则返回 None。"""
    for py in candidate_pythons():
        if has_ursina(py):
            return py
    return None


def install_deps(py):
    """用指定解释器安装 requirements.txt, 返回是否成功。"""
    try:
        r = subprocess.run([py, "-m", "pip", "install", "-r", REQS],
                           capture_output=True, timeout=600,
                           creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def launch_game(py):
    subprocess.Popen([py, MAIN], cwd=HERE, creationflags=CREATE_NO_WINDOW)


def run_tests(py):
    """跑无头测试套件, 返回输出文本。"""
    try:
        r = subprocess.run([py, TESTS], capture_output=True, text=True,
                           timeout=300, cwd=HERE, creationflags=CREATE_NO_WINDOW)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "运行失败: %r" % e


def read_hiscore():
    try:
        with open(HI_FILE, encoding="utf-8") as f:
            return int(json.load(f).get("hiscore", 0))
    except Exception:
        return 0


# ---------------------------------------------------------------- 图形界面
BG = "#0a1024"
BG_PANEL = "#13204a"
FG = "#cfe0ff"
ACCENT = "#7fe0ff"
GOLD = "#ffd280"


class Launcher:
    def __init__(self, root):
        self.root = root
        self.python = None
        root.title("三维弹球 · 太空军校生 — 启动器")
        root.configure(bg=BG)
        root.geometry("420x360")
        root.resizable(False, False)

        tk.Label(root, text="🚀 三维弹球 · 太空军校生", bg=BG, fg=ACCENT,
                 font=FONT_TITLE).pack(pady=(22, 2))
        tk.Label(root, text="现代化重制版 · Ursina", bg=BG, fg="#5a6f9e",
                 font=("Microsoft YaHei UI", 9)).pack()

        self.hiscore = tk.Label(root, text="", bg=BG, fg=GOLD, font=FONT)
        self.hiscore.pack(pady=(10, 4))

        panel = tk.Frame(root, bg=BG_PANEL)
        panel.pack(padx=24, fill="x")
        self.status = tk.Label(panel, text="正在检测 Python 环境…", bg=BG_PANEL,
                               fg=FG, font=("Microsoft YaHei UI", 9), wraplength=360)
        self.status.pack(padx=12, pady=(10, 6))

        btns = tk.Frame(root, bg=BG)
        btns.pack(pady=14)
        self.btn_play = self._btn(btns, "▶  开始游戏", self.on_play, "#1c5fd0")
        self.btn_test = self._btn(btns, "运行自检", self.on_test, "#2a3a66")
        self.btn_help = self._btn(btns, "操作说明", self.on_help, "#2a3a66")
        self.btn_install = self._btn(btns, "安装依赖", self.on_install, "#a05a1c")

        self._set_enabled(self.btn_play, False)
        self._set_enabled(self.btn_test, False)
        self._set_enabled(self.btn_install, False)

        tk.Label(root, text="游戏目录: %s" % HERE, bg=BG, fg="#3d4f78",
                 font=("Microsoft YaHei UI", 8), wraplength=380).pack(side="bottom",
                                                                      pady=6)
        self.root.after(80, self.detect)

    def _btn(self, parent, text, cmd, bg):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg="white",
                      activebackground="#35508f", activeforeground="white",
                      relief="flat", padx=16, pady=7, font=FONT, cursor="hand2",
                      state="normal")
        b.pack(side="left", padx=6)
        return b

    def _set_enabled(self, btn, enabled):
        btn.configure(state="normal" if enabled else "disabled")

    def detect(self):
        self.python = find_python()
        self.refresh_hiscore()
        if self.python:
            self.status.configure(
                text="✓ 环境就绪:  %s" % self.python, fg="#7be2a0")
            self._set_enabled(self.btn_play, True)
            self._set_enabled(self.btn_test, True)
        else:
            cands = candidate_pythons()
            if cands:
                self.status.configure(
                    text="✗ 找到 Python 但缺少 Ursina 依赖:\n%s\n点击「安装依赖」一键安装。"
                         % cands[0], fg="#ff9a9a")
                self._install_target = cands[0]
                self._set_enabled(self.btn_install, True)
            else:
                self.status.configure(
                    text="✗ 未找到 Python。请安装 Anaconda 后重试。", fg="#ff9a9a")

    def refresh_hiscore(self):
        hi = read_hiscore()
        self.hiscore.configure(
            text="★ 最高分  %s" % format(hi, ",") if hi else "★ 尚无纪录, 等你创造")

    def on_play(self):
        if not self.python:
            return
        launch_game(self.python)
        self.root.after(400, self.root.destroy)

    def on_test(self):
        if not self.python:
            return
        self.status.configure(text="自检运行中, 约 10~30 秒…", fg=FG)
        self.root.update_idletasks()
        out = run_tests(self.python).strip()
        tail = "\n".join(out.splitlines()[-6:])
        ok = "passed" in tail and "FAIL" not in tail and "ERROR" not in tail
        messagebox.showinfo(
            "自检结果" if ok else "自检发现问题",
            tail if tail else "(无输出)")
        self.refresh_hiscore()

    def on_help(self):
        messagebox.showinfo("操作说明",
            "Z / ←          左弹板\n"
            "/ 或 →          右弹板\n"
            "空格或 ↓ 按住    发射杆蓄力, 松开发射\n"
            "X / . / ↑       推台(连续会 TILT)\n"
            "F1 帮助    F2 新游戏    P 暂停    Esc 退出\n\n"
            "玩法: 击中任务靶开启任务, 完成任务晋升军衔;\n"
            "集齐奖章降落靶提倍率; 超空间 5 级 → 多球;\n"
            "黄/绿虫洞互相传送。")

    def on_install(self):
        py = getattr(self, "_install_target", None)
        if not py:
            return
        self.status.configure(text="正在安装依赖(ursina), 可能需要几分钟…", fg=FG)
        self.root.update_idletasks()
        if install_deps(py) and has_ursina(py):
            self.python = py
            self.status.configure(text="✓ 安装完成:  %s" % py, fg="#7be2a0")
            self._set_enabled(self.btn_play, True)
            self._set_enabled(self.btn_test, True)
            self._set_enabled(self.btn_install, False)
        else:
            messagebox.showerror("安装失败",
                                 "请手动运行:\n%s -m pip install -r requirements.txt" % py)


def main():
    root = tk.Tk()
    Launcher(root)
    root.mainloop()


# ---------------------------------------------------------------- 命令行模式
def cli_check():
    print("候选解释器:")
    for p in candidate_pythons():
        print("  %s %s" % ("[ursina✓]" if has_ursina(p) else "[无依赖 ]", p))
    py = find_python()
    print("\n选用: %s" % (py or "(无)"))
    print("最高分: %s" % format(read_hiscore(), ","))


def cli_launch():
    py = find_python()
    if not py:
        cands = candidate_pythons()
        if cands and install_deps(cands[0]):
            py = cands[0]
    if not py:
        print("未找到带 Ursina 的 Python, 请先安装依赖")
        sys.exit(1)
    print("使用 %s 启动游戏…" % py)
    launch_game(py)


if __name__ == "__main__":
    if "--check" in sys.argv:
        cli_check()
    elif "--launch" in sys.argv:
        cli_launch()
    else:
        main()
