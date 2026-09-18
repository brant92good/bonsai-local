$ErrorActionPreference = 'Stop'
$runtimePaths = @(
    [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'bin\llama-server.exe')),
    [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'mtp\llama\build\bin\llama-server.exe'))
)
$targets = @(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object {
    $_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath) -in $runtimePaths
})
foreach ($target in $targets) {
    Stop-Process -Id $target.ProcessId -ErrorAction Stop
    Write-Host "Stopped Bonsai process $($target.ProcessId)."
}
if ($targets.Count -eq 0) { Write-Host 'Bonsai is already stopped.' }
