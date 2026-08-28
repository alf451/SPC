@echo off
REM Doppio click per installare - non serve cambiare l'execution policy di PowerShell
REM ne' avere privilegi di amministratore (-ExecutionPolicy Bypass vale solo per questo processo).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
