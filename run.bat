@echo off
cd /d "%~dp0"
.\.venv\Scripts\python.exe -m screener.cli %*
start "" "output\dashboard.html"
