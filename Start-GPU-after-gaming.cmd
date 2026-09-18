@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Bonsai.ps1" -EnableGpu -Mtp -Profile balanced -BatchSize 2048 -MicroBatchSize 512
pause
