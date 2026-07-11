@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_release.ps1"
exit /b %ERRORLEVEL%
