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
    'balanced'   = @{ ContextPool = 204800; Slots = 2; Batch = 2048; MicroBatch = 512 }
    'single-200k'= @{ ContextPool = 204800; Slots = 1; Batch = 1024; MicroBatch = 256 }
    'agents-4'   = @{ ContextPool = 204800; Slots = 4; Batch = 2048; MicroBatch = 512 }
    'agents-8'   = @{ ContextPool = 204800; Slots = 8; Batch = 2048; MicroBatch = 512 }
}
$target = $profiles[$ServingProfile]

function Get-LoadedRuntime {
    try {
        $props = Invoke-RestMethod 'http://127.0.0.1:18080/props' -TimeoutSec 2
        $listener = Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction Stop | Select-Object -First 1
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        $arguments = [string]$process.CommandLine
        [pscustomobject]@{
            Model = [string]$props.model_alias
            ContextPool = [int]$props.default_generation_settings.n_ctx
            Slots = [int]$props.total_slots
            UnifiedKv = $arguments -match '(?:^|\s)--kv-unified(?:\s|$)' -and $arguments -notmatch '(?:^|\s)--no-kv-unified(?:\s|$)'
        }
    } catch {
        $null
    }
}

$active = Get-LoadedRuntime
$reused = (-not $ForceRestart) -and $active -and
    $active.Model -eq $expectedModel -and
    $active.ContextPool -eq $target.ContextPool -and
    $active.Slots -eq $target.Slots -and
    $active.UnifiedKv
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
    $runStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdout = Join-Path $logDir "$Variant-$ServingProfile-$runStamp.stdout.log"
    $stderr = Join-Path $logDir "$Variant-$ServingProfile-$runStamp.stderr.log"
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
    } while ((-not $active -or $active.Model -ne $expectedModel -or $active.ContextPool -ne $target.ContextPool -or $active.Slots -ne $target.Slots -or -not $active.UnifiedKv) -and [DateTime]::UtcNow -lt $deadline)

    if (-not $active -or $active.Model -ne $expectedModel -or $active.ContextPool -ne $target.ContextPool -or $active.Slots -ne $target.Slots -or -not $active.UnifiedKv) {
        & (Join-Path $root 'Stop-Bonsai.ps1')
        throw "Timed out waiting for $expectedModel with a $($target.ContextPool)-token unified KV pool and $($target.Slots) slot(s)."
    }
}
[pscustomobject]@{
    Variant = $Variant
    Profile = $ServingProfile
    Model = $expectedModel
    ContextPool = $target.ContextPool
    Slots = $target.Slots
    UnifiedKv = $true
    Api = 'http://127.0.0.1:18080/v1'
    Reused = [bool]$reused
}
