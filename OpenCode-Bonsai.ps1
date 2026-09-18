[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path,
    [switch]$Abliterated
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$model = if ($Abliterated) { 'bonsai/bonsai2-27b-abliterated' } else { 'bonsai/bonsai2-27b' }
$variant = if ($Abliterated) { 'abliterated' } else { 'standard' }
if (-not (Test-Path -LiteralPath $project -PathType Container)) { throw 'ProjectPath must be a directory.' }
$binary = Join-Path $PSScriptRoot 'clients\opencode\opencode.exe'
if (-not (Test-Path -LiteralPath $binary)) { throw 'Run Setup.ps1 to install OpenCode.' }
$selection = & (Join-Path $PSScriptRoot 'Switch-Bonsai.ps1') -Variant $variant
Write-Host "Using $($selection.Model) at $($selection.Api)" -ForegroundColor Green
$keys = @('OPENCODE_CONFIG','OPENCODE_CONFIG_CONTENT','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME')
$previous = @{}
foreach ($key in $keys) { $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
try {
    $env:OPENCODE_CONFIG = Join-Path $PSScriptRoot 'opencode.bonsai.example.json'
    $env:OPENCODE_CONFIG_CONTENT = Get-Content -LiteralPath $env:OPENCODE_CONFIG -Raw
    foreach ($kind in @('CONFIG','DATA','CACHE','STATE')) {
        $path = Join-Path $PSScriptRoot "clients\opencode\user-state\$($kind.ToLower())"
        $null = New-Item -ItemType Directory -Path $path -Force
        [Environment]::SetEnvironmentVariable("XDG_${kind}_HOME", $path, 'Process')
    }
    & $binary $project --pure --model $model
    $result = $LASTEXITCODE
} finally {
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
}
exit $result
