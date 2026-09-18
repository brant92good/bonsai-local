@echo off
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0OpenCode-Bonsai.ps1"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0OpenCode-Bonsai.ps1" -ProjectPath "%~1"
)
