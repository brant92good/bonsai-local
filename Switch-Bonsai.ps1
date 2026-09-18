[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('standard','abliterated')]
    [string]$Variant,
    [ValidateSet('balanced','single-200k','agents-4','agents-8')]
    [string]$ServingProfile = 'balanced',
    [ValidateRange(10,300)]
    [int]$StartupTimeoutSeconds = 120,
    [string]$LogDirectory = (Join-Path $PSScriptRoot 'logs'),
    [switch]$ForceRestart
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$expectedModel = if ($Variant -eq 'abliterated') { 'bonsai2-27b-abliterated' } else { 'bonsai2-27b' }
$profiles = @{
    'balanced'   = @{ Context = 131072; Slots = 2; Batch = 2048; MicroBatch = 512 }
    'single-200k'= @{ Context = 204800; Slots = 1; Batch = 1024; MicroBatch = 256 }
    'agents-4'   = @{ Context = 32768;  Slots = 4; Batch = 2048; MicroBatch = 512 }
    'agents-8'   = @{ Context = 16384;  Slots = 8; Batch = 2048; MicroBatch = 512 }
}
$target = $profiles[$ServingProfile]

function Get-LoadedRuntime {
    try {
        $props = Invoke-RestMethod 'http://127.0.0.1:18080/props' -TimeoutSec 2
        [pscustomobject]@{
            Model = [string]$props.model_alias
            Context = [int]$props.default_generation_settings.n_ctx
            Slots = [int]$props.total_slots
        }
    } catch {
        $null
    }
}

$active = Get-LoadedRuntime
$reused = (-not $ForceRestart) -and $active -and
    $active.Model -eq $expectedModel -and
    $active.Context -eq $target.Context -and
    $active.Slots -eq $target.Slots
if (-not $reused) {
    & (Join-Path $root 'Stop-Bonsai.ps1')
    Start-Sleep -Milliseconds 500
    $listener = Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw 'Port 18080 is owned by another application.' }

    $logDir = [IO.Path]::GetFullPath($LogDirectory)
    $null = New-Item -ItemType Directory -Path $logDir -Force
    $launchArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $root 'Start-Bonsai.ps1'),
        '-EnableGpu', '-Profile', $ServingProfile,
        '-BatchSize', "$($target.Batch)", '-MicroBatchSize', "$($target.MicroBatch)"
    )
    if ($Variant -eq 'abliterated') { $launchArgs += '-Abliterated' } else { $launchArgs += '-Mtp' }
    $stdout = Join-Path $logDir "$Variant-$ServingProfile.stdout.log"
    $stderr = Join-Path $logDir "$Variant-$ServingProfile.stderr.log"
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
            throw "The $Variant $ServingProfile model failed to start. $tail"
        }
        Start-Sleep -Seconds 1
        $active = Get-LoadedRuntime
    } while ((-not $active -or $active.Model -ne $expectedModel -or $active.Context -ne $target.Context -or $active.Slots -ne $target.Slots) -and [DateTime]::UtcNow -lt $deadline)

    if (-not $active -or $active.Model -ne $expectedModel -or $active.Context -ne $target.Context -or $active.Slots -ne $target.Slots) {
        & (Join-Path $root 'Stop-Bonsai.ps1')
        throw "Timed out waiting for $expectedModel with $($target.Context) context and $($target.Slots) slot(s)."
    }
}
[pscustomobject]@{
    Variant = $Variant
    Profile = $ServingProfile
    Model = $expectedModel
    Context = $target.Context
    Slots = $target.Slots
    Api = 'http://127.0.0.1:18080/v1'
    Reused = [bool]$reused
}
