@echo off
title JanSetu IVR Telephony Simulator
echo ========================================================
echo Launching JanSetu IVR Telephony Simulator CLI
echo ========================================================
cd /d "%~dp0\backend"
set PYTHONIOENCODING=utf-8
"..\.venv\Scripts\python.exe" -m app.channels.simulator
pause
