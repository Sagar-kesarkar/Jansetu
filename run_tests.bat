@echo off
title JanSetu Pytest Test Suite
echo ========================================================
echo Running JanSetu Backend Test Suite (82 tests)
echo ========================================================
cd /d "%~dp0\backend"
set PYTHONIOENCODING=utf-8
"..\.venv\Scripts\python.exe" -m pytest -v
pause
