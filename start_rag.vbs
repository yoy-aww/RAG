Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """C:\yoyac-work\RAG\.venv\Scripts\python.exe"" -m uvicorn src.rag.api.app:app --host 0.0.0.0 --port 8000", 0, False
WshShell.CurrentDirectory = "C:\yoyac-work\RAG"
