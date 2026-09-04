"""RAG 服务 —— 用 pythonw 启动，脱离 Hermes 控制台。
双击运行此脚本即可。
"""
import os
import subprocess
import sys
import time

PORT = 8000
RAG_DIR = r"C:\yoyac-work\RAG"
PYTHONW = os.path.join(RAG_DIR, ".venv", "Scripts", "pythonw.exe")

if not os.path.exists(PYTHONW):
    PYTHONW = r"C:\Users\aww\AppData\Local\Programs\Python\Python311\pythonw.exe"

if not os.path.exists(PYTHONW):
    import tkinter as tk
    from tkinter.messagebox import showerror
    showerror("错误", f"找不到 pythonw.exe\n期望路径: {PYTHONW}")
    sys.exit(1)

# 检查端口是否已占用
import urllib.request
try:
    urllib.request.urlopen(f"http://localhost:{PORT}/info", timeout=3)
    import tkinter as tk
    from tkinter.messagebox import showinfo
    showinfo("提示", "RAG 已经在运行中")
    sys.exit(0)
except:
    pass

# 启动 RAG（pythonw 无控制台，脱离 Hermes）
os.chdir(RAG_DIR)
subprocess.Popen(
    [PYTHONW, "-m", "uvicorn", "src.rag.api.app:app",
     "--host", "0.0.0.0", "--port", str(PORT)],
    cwd=RAG_DIR,
    creationflags=subprocess.DETACHED_PROCESS,
)

print(f"RAG started on port {PORT} (pythonw, detached)")
print("Log: check terminal output or rag.log")
