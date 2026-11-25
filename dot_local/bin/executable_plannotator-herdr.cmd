@echo off
powershell.exe -NoProfile -File "%~dp0plannotator-herdr.ps1" %*
exit /b %ERRORLEVEL%
