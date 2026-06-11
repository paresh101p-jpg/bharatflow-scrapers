@echo off
echo Running News Sync Job...
cd /d "%~dp0"
node news_sync.js
echo Done.
pause
