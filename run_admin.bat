@echo off
title JanSetu Officials Console (:5174)
echo ========================================================
echo Starting JanSetu Officials Console on http://localhost:5174
echo ========================================================
cd /d "%~dp0\frontend-admin"
call npm.cmd run dev
pause
