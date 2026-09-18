[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('standard','abliterated')]
    [string]$Variant,
    [ValidateRange(10,300)]
    [int]$StartupTimeoutSeconds = 120
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$expected = if ($Variant -eq 'abliterated') { 'bonsai2-27b-abliterated' } else { 'bonsai2-27b' }

function Get-LoadedModel {
    try {
        $models = Invoke-RestMethod 'http://127.0.0.1:18080/v1/models' -TimeoutSec 2
        return @($models.data.id)[0]
    } catch {
        return $null
    }
}

$loaded = Get-LoadedModel
$reused = $loaded -eq $expected
if (-not $reused) {
    & (Join-Path $root 'Stop-Bonsai.ps1')
    Start-Sleep -Milliseconds 500
    $listener = Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw 'Port 18080 is owned by another application.' }

    $logDir = Join-Path $root 'logs'
    $null = New-Item -ItemType Directory -Path $logDir -Force
    $launchArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $root 'Start-Bonsai.ps1'),
        '-EnableGpu', '-Profile', 'balanced',
        '-BatchSize', '2048', '-MicroBatchSize', '512'
    )
    if ($Variant -eq 'abliterated') { $launchArgs += '-Abliterated' } else { $launchArgs += '-Mtp' }
    $stdout = Join-Path $logDir "$Variant.stdout.log"
    $stderr = Join-Path $logDir "$Variant.stderr.log"
    $startParams = @{
        FilePath = 'powershell.exe'
        ArgumentList = $launchArgs
        WindowStyle = 'Hidden'
        PassThru = $true
        RedirectStandardOutput = $stdout
        RedirectStandardError = $stderr
    }
    $process = Start-Process @startParams

    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    do {
        if ($process.HasExited) {
            $tail = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Tail 40 | Out-String } else { '' }
            throw "The $Variant model failed to start. $tail"
        }
        Start-Sleep -Seconds 1
        $loaded = Get-LoadedModel
    } while ($loaded -ne $expected -and [DateTime]::UtcNow -lt $deadline)

    if ($loaded -ne $expected) {
        & (Join-Path $root 'Stop-Bonsai.ps1')
        throw "Timed out waiting for $expected."
    }
}
[pscustomobject]@{
    Variant = $Variant
    Model = $expected
    Api = 'http://127.0.0.1:18080/v1'
    Reused = $reused
}
