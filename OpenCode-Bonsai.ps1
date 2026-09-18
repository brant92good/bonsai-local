[CmdletBinding()]
param([string]$ProjectPath = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath $project -PathType Container)) { throw 'ProjectPath must be a directory.' }
$binary = Join-Path $PSScriptRoot 'clients\opencode\opencode.exe'
if (-not (Test-Path -LiteralPath $binary)) { throw 'Run Setup.ps1 to install OpenCode.' }
try { $null = Invoke-RestMethod 'http://127.0.0.1:18080/health' -TimeoutSec 3 } catch { throw 'Start the Bonsai server with Start-GPU-after-gaming.cmd first.' }
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
    & $binary $project --pure --model 'bonsai/bonsai2-27b'
    $result = $LASTEXITCODE
} finally {
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
}
exit $result
