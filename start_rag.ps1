$proc = Start-Process -FilePath "C:\yoyac-work\RAG\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','src.rag.api.app:app','--host','0.0.0.0','--port','8000' -WorkingDirectory "C:\yoyac-work\RAG" -WindowStyle Hidden -PassThru
Write-Output "Started PID: $($proc.Id)"
