[CmdletBinding()]
param(
    [switch]$EnableGpu,
    [switch]$Mtp,
    [switch]$Abliterated,
    [switch]$DisableSpeculation,
    [ValidateRange(1,8)][int]$DraftTokens = 4,
    [ValidateSet('PTQ1_0','PQ2_0')][string]$Packing = 'PQ2_0',
    [ValidateSet('baseline','balanced','single-200k','agents-4','agents-8','long-context')][string]$Profile = 'balanced',
    [ValidateSet('f16','q8_0','q4_0')][string]$CacheTypeK = 'q8_0',
    [ValidateSet('f16','q8_0','q4_0')][string]$CacheTypeV = 'q8_0',
    [string]$KvMeanCenterFile,
    [ValidateRange(128,8192)][int]$BatchSize = 512,
    [ValidateRange(64,2048)][int]$MicroBatchSize = 256,
    [Alias('Users')][ValidateRange(1,8)][int]$ParallelRequests = 2,
    [ValidateRange(2048,262144)][int]$ContextPerUser = 131072,
    [switch]$Vision,
    [ValidateSet('127.0.0.1','0.0.0.0')][string]$ListenAddress = '127.0.0.1',
    [ValidateRange(1024,65535)][int]$Port = 18080,
    [string]$ApiKeyFile
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if ($Abliterated) {
    $Mtp = $true
    if (-not $PSBoundParameters.ContainsKey('DraftTokens')) { $DraftTokens = 2 }
}
if ($MicroBatchSize -gt $BatchSize) { throw 'MicroBatchSize must not exceed BatchSize.' }
$profiles = @{
    'baseline'      = @{Parallel=2; Context=65536;  Cache='f16'}
    'balanced'      = @{Parallel=2; Context=131072; Cache='q8_0'}
    'single-200k'    = @{Parallel=1; Context=204800; Cache='q8_0'}
    'agents-4'       = @{Parallel=4; Context=32768;  Cache='q8_0'}
    'agents-8'       = @{Parallel=8; Context=16384;  Cache='q8_0'}
    'long-context'  = @{Parallel=1; Context=262144; Cache='q8_0'}
}
$preset = $profiles[$Profile]
if (-not $PSBoundParameters.ContainsKey('ParallelRequests')) { $ParallelRequests = $preset.Parallel }
if (-not $PSBoundParameters.ContainsKey('ContextPerUser')) { $ContextPerUser = $preset.Context }
if (-not $PSBoundParameters.ContainsKey('CacheTypeK')) { $CacheTypeK = $preset.Cache }
if (-not $PSBoundParameters.ContainsKey('CacheTypeV')) { $CacheTypeV = $preset.Cache }
$runtimePaths = @((Join-Path $root 'bin\llama-server.exe'), (Join-Path $root 'mtp\llama\build\bin\llama-server.exe'))
if ($Mtp) { $binary = @(Get-Item -LiteralPath $runtimePaths[1] -ErrorAction SilentlyContinue); $Packing = 'PQ2_0' } else { $binary = @(Get-Item -LiteralPath $runtimePaths[0] -ErrorAction SilentlyContinue) }
if ($DisableSpeculation -and -not $Mtp) { throw 'DisableSpeculation is a benchmark control for the MTP model.' }
if ($binary.Count -ne 1) { throw 'Expected exactly one installed llama-server.exe. Run Setup.ps1 first.' }
$modelAlias = 'bonsai2-27b'
$model = Join-Path $root ("models\Ternary-Bonsai-2-27B-$Packing.gguf")
if ($Mtp) { $model = Join-Path $root 'models\Ternary-Bonsai-2-27B-PQ2_0-MTP-Q8_0.gguf' }
if ($Abliterated) {
    $model = Join-Path $root 'models\Ternary-Bonsai-2-27B-Abliterated-PQ2_0-MTP.gguf'
    $modelAlias = 'bonsai2-27b-abliterated'
}
$projector = Join-Path $root 'models\Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf'
$totalContext = [long]$ParallelRequests * $ContextPerUser
$serverArgs = @(
    '--model', $model,
    '--alias', $modelAlias,
    '--host', $ListenAddress, '--port', "$Port",
    '--n-gpu-layers', '99', '--flash-attn', 'on',
    '--ctx-size', "$totalContext", '--parallel', "$ParallelRequests",
    '--cont-batching', '--cache-prompt', '--metrics', '--no-kv-unified', '--cache-type-k', $CacheTypeK, '--cache-type-v', $CacheTypeV,
    '--batch-size', "$BatchSize", '--ubatch-size', "$MicroBatchSize",
    '--temp', '1.0', '--top-p', '0.95', '--top-k', '20', '--min-p', '0',
    '--repeat-penalty', '1.0', '--presence-penalty', '0.0',
    '--jinja', '--reasoning-format', 'deepseek', '--fit', 'off'
)
if ($Mtp) {
    $specType = if ($DisableSpeculation) { 'none' } else { 'draft-mtp' }
    $serverArgs += @('--spec-type', $specType, '--spec-draft-n-max', "$DraftTokens")
}
if ($KvMeanCenterFile) {
    if ($CacheTypeK -ne 'q4_0') { throw 'Mean-centering requires Q4_0 K cache.' }
    if (-not (Test-Path -LiteralPath $KvMeanCenterFile -PathType Leaf)) { throw 'Mean-centering bias file does not exist; calibration must be run after GPU authorization.' }
    $serverArgs += @('--kv-mean-center', (Resolve-Path -LiteralPath $KvMeanCenterFile).Path)
}
if ($Vision) { $serverArgs += @('--mmproj', $projector) }
if ($ListenAddress -eq '0.0.0.0' -and -not $ApiKeyFile) {
    throw 'LAN access requires -ApiKeyFile with a private file containing one API key per line.'
}
if ($ApiKeyFile) {
    if (-not (Test-Path -LiteralPath $ApiKeyFile -PathType Leaf)) { throw 'API key file is missing.' }
    if ([string]::IsNullOrWhiteSpace((Get-Content -LiteralPath $ApiKeyFile -Raw))) { throw 'API key file is empty.' }
    $serverArgs += @('--api-key-file', (Resolve-Path -LiteralPath $ApiKeyFile).Path)
}
$weightSizes = @{PTQ1_0=5946648928; PQ2_0=7206168928}
$weightsBytes = if ($Abliterated) { 7657489696 } elseif ($Mtp) { 7657489728 } else { $weightSizes[$Packing] }
$weightsGiB = $weightsBytes / 1GB
$cacheKiBPerSide = @{f16=32; q8_0=17; q4_0=9}
$cacheGiB = $totalContext * ($cacheKiBPerSide[$CacheTypeK] + $cacheKiBPerSide[$CacheTypeV]) * 1KB / 1GB
if ($Mtp) { Write-Host "MTP model; speculative mode: $specType; draft tokens: $DraftTokens" }
Write-Host "Bonsai 2 ${Packing}: $ParallelRequests concurrent request(s), $ContextPerUser tokens per request."
Write-Host "Profile: $Profile. K=$CacheTypeK V=$CacheTypeV cache: $cacheGiB GiB; weights: $([math]::Round($weightsGiB,2)) GiB; runtime overhead is additional."
Write-Host "API: http://127.0.0.1:$Port/v1 ; model: $modelAlias"
if (-not $EnableGpu) {
    Write-Host 'PREVIEW ONLY. No model process started. Add -EnableGpu when you are done gaming.' -ForegroundColor Green
    [pscustomobject]@{Executable=$binary[0].FullName; Arguments=$serverArgs; GpuStarted=$false} | ConvertTo-Json -Depth 3
    return
}
foreach ($required in @($model) + $(if($Vision){@($projector)}else{@()})) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing model file: $required" }
}
$verifiedPath = Join-Path $root 'verification.json'
if (-not (Test-Path -LiteralPath $verifiedPath)) { throw 'Installation has not completed checksum verification.' }
$verified = Get-Content -LiteralPath $verifiedPath -Raw | ConvertFrom-Json
foreach ($required in @($model) + $(if($Vision){@($projector)}else{@()})) {
    $entry = @($verified | Where-Object { $_.file -eq $required -and $_.verified -eq $true })
    if ($entry.Count -ne 1 -or (Get-Item -LiteralPath $required).Length -ne $entry[0].bytes) {
        throw "Model has not passed install verification: $required"
    }
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is already in use." }
if (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object { $_.ExecutablePath -in $runtimePaths }) {
    throw 'This Bonsai runtime is already running. Stop it before starting another copy.'
}
Write-Host 'GPU inference is starting now. Press Ctrl+C here, or run Stop-Bonsai.cmd, to release its VRAM.' -ForegroundColor Yellow
$oldPath = $env:Path
$oldCuda = $env:CUDA_VISIBLE_DEVICES
$oldRotDisable = $env:LLAMA_ATTN_ROT_DISABLE
try {
    $env:Path = "$($binary[0].DirectoryName);$env:CUDA_PATH\bin\x64;$env:CUDA_PATH\bin;$root\bin;$oldPath"
    $env:CUDA_VISIBLE_DEVICES = '0'
    if ($KvMeanCenterFile) { $env:LLAMA_ATTN_ROT_DISABLE = '1' }
    & $binary[0].FullName @serverArgs
    $serverExitCode = $LASTEXITCODE
} finally {
    $env:Path = $oldPath
    $env:CUDA_VISIBLE_DEVICES = $oldCuda
    $env:LLAMA_ATTN_ROT_DISABLE = $oldRotDisable
}
exit $serverExitCode
