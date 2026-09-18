[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\OpenCode')
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'clients\opencode\opencode.exe'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw 'Run Setup.ps1 first so the pinned OpenCode release is downloaded and verified.'
}
$null = New-Item -ItemType Directory -Path $InstallDir -Force
$target = Join-Path $InstallDir 'opencode.exe'
$sameBinary = (Test-Path -LiteralPath $target -PathType Leaf) -and
    ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -eq
     (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash)
if (-not $sameBinary) { Copy-Item -LiteralPath $source -Destination $target -Force }

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($userPath -split ';' | Where-Object { $_ })
if ($InstallDir -notin $parts) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $InstallDir) -join ';'), 'User')
}
if ($InstallDir -notin @($env:Path -split ';')) { $env:Path = "$InstallDir;$env:Path" }

$configDir = Join-Path $env:USERPROFILE '.config\opencode'
$configPath = Join-Path $configDir 'opencode.json'
$null = New-Item -ItemType Directory -Path $configDir -Force
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
} else {
    $config = [pscustomobject]@{}
}
$config | Add-Member NoteProperty '$schema' 'https://opencode.ai/config.json' -Force
if (-not $config.provider) { $config | Add-Member NoteProperty provider ([pscustomobject]@{}) -Force }
$models = [ordered]@{
    'bonsai2-27b' = [ordered]@{
        name = 'Bonsai 2 27B - Standard MTP (draft 4)'
        limit = [ordered]@{ context = 131072; output = 8192 }
    }
    'bonsai2-27b-abliterated' = [ordered]@{
        name = 'Bonsai 2 27B - Abliterated MTP (draft 2)'
        limit = [ordered]@{ context = 131072; output = 8192 }
    }
}
$bonsai = [ordered]@{
    name = 'Bonsai local'
    npm = '@ai-sdk/openai-compatible'
    options = [ordered]@{
        apiKey = 'local-bonsai'
        baseURL = 'http://127.0.0.1:18080/v1'
    }
    models = $models
}
$config.provider | Add-Member NoteProperty bonsai $bonsai -Force
$config | Add-Member NoteProperty model 'bonsai/bonsai2-27b' -Force
if ($config.enabled_providers) {
    $enabled = @($config.enabled_providers)
    if ('bonsai' -notin $enabled) { $enabled += 'bonsai' }
    $config | Add-Member NoteProperty enabled_providers $enabled -Force
}
$config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $configPath -Encoding UTF8

$standardCommand = @'
@echo off
set "BONSAI_PROJECT=%~1"
if "%BONSAI_PROJECT%"=="" set "BONSAI_PROJECT=%CD%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "__ROOT__\OpenCode-Bonsai.ps1" -ProjectPath "%BONSAI_PROJECT%"
'@.Replace('__ROOT__', $PSScriptRoot)
$abliteratedCommand = @'
@echo off
set "BONSAI_PROJECT=%~1"
if "%BONSAI_PROJECT%"=="" set "BONSAI_PROJECT=%CD%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "__ROOT__\OpenCode-Bonsai.ps1" -Abliterated -ProjectPath "%BONSAI_PROJECT%"
'@.Replace('__ROOT__', $PSScriptRoot)
Set-Content -LiteralPath (Join-Path $InstallDir 'bonsai-standard.cmd') -Value $standardCommand -Encoding ASCII
Set-Content -LiteralPath (Join-Path $InstallDir 'bonsai-abliterated.cmd') -Value $abliteratedCommand -Encoding ASCII

Write-Host "OpenCode $(& $target --version) installed at $target"
Write-Host "Config: $configPath"
Write-Host 'Commands: bonsai-standard, bonsai-abliterated'
