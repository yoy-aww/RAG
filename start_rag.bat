@echo off
title RAG Server
echo Starting RAG Server...
cd /d C:\yoyac-work\RAG
:loop
.venv\Scripts\python.exe -m uvicorn src.rag.api.app:app --host 0.0.0.0 --port 8000
echo.
echo [ERROR] RAG crashed, restarting in 3s...
timeout /t 3
goto loop
