[CmdletBinding()]
param(
    [string]$InstallDir = $PSScriptRoot,
    [string]$Python = 'python',
    [switch]$SkipBuild,
    [switch]$AllModels,
    [switch]$Abliterated,
    [ValidateRange(50,120)][int]$CudaArchitecture = 86
)
$ErrorActionPreference = 'Stop'
$setupArgs = @((Join-Path $PSScriptRoot 'tools\setup.py'), '--install-dir', $InstallDir, '--cuda-architecture', "$CudaArchitecture")
if ($SkipBuild) { $setupArgs += '--skip-build' }
if ($AllModels) { $setupArgs += '--all-models' }
if ($Abliterated) { $setupArgs += '--abliterated' }
& $Python @setupArgs
if ($LASTEXITCODE -ne 0) { throw "Setup failed with exit code $LASTEXITCODE." }
