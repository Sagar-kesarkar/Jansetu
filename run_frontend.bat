@echo off
title JanSetu Citizen Web App (:5173)
echo ========================================================
echo Starting JanSetu Citizen Web App on http://localhost:5173
echo ========================================================
cd /d "%~dp0\frontend"
call npm.cmd run dev
pause
