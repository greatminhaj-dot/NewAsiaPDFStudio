@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (echo BUILD FAILED) else (echo BUILD COMPLETE)
pause
