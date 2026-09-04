"""RAG 守护进程启动器 —— 双 fork 脱离 Hermes 管理。
用法: python start_daemon.py
"""
import os
import subprocess
import sys
import time
import signal
import ctypes

def daemonize():
    """Windows 双 fork：第一次用 CREATE_NEW_PROCESS_GROUP 脱离控制台，
    第二次用 DETACHED_PROCESS 彻底脱离进程树。"""
    python = sys.executable
    script = os.path.abspath(__file__)
    
    # 启动一个完全脱离的进程
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [python, script, "--daemon"],
        creationflags=flags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )

def run_daemon():
    """实际运行 RAG，崩溃后自动重启。"""
    import os as _os
    _os.chdir(r"C:\yoyac-work\RAG")
    _os.environ["PYTHONUNBUFFERED"] = "1"
    
    log = open(r"C:\yoyac-work\RAG\rag.log", "a", encoding="utf-8")
    log.write(f"\n{'='*40}\n[DAEMON] Started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.flush()
    
    while True:
        try:
            proc = subprocess.Popen(
                [r"C:\yoyac-work\RAG\.venv\Scripts\python.exe",
                 "-m", "uvicorn", "src.rag.api.app:app",
                 "--host", "0.0.0.0", "--port", "8000"],
                cwd=r"C:\yoyac-work\RAG",
                stdout=log, stderr=log,
            )
            proc.wait()
            log.write(f"[DAEMON] RAG exited with code {proc.returncode}, restarting in 3s...\n")
            log.flush()
            time.sleep(3)
        except Exception as e:
            log.write(f"[DAEMON] Error: {e}, restarting in 3s...\n")
            log.flush()
            time.sleep(3)

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        run_daemon()
    else:
        daemonize()
        print("RAG daemon started (detached). Check C:\\yoyac-work\\RAG\\rag.log")
