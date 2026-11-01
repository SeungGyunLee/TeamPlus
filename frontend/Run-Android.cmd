@echo off
title KW Meet - Android
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-KWMeet.ps1" -Task emulator
pause
