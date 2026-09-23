@echo off
title JanSetu Backend (FastAPI :8080)
echo ========================================================
echo Starting JanSetu Backend API on http://localhost:8080
echo API Docs: http://localhost:8080/docs
echo ========================================================
cd /d "%~dp0\backend"
set PYTHONIOENCODING=utf-8
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --port 8080
pause
