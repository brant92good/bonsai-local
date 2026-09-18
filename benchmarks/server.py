import contextlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import benchmark as b


def stop_owned():
    env = os.environ.copy()
    env['BONSAI_BENCH_ROOT'] = str(b.ROOT)
    command = r"""
$listener = Get-NetTCPConnection -LocalPort 18081 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listener.OwningProcess)
    $owned = @((Join-Path $env:BONSAI_BENCH_ROOT 'bin\llama-server.exe'), (Join-Path $env:BONSAI_BENCH_ROOT 'mtp\llama\build\bin\llama-server.exe'))
    if ($process.ExecutablePath -notin $owned) { throw 'Unexpected benchmark port owner.' }
    Stop-Process -Id $listener.OwningProcess -ErrorAction Stop
}
"""
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], env=env,
                   check=True, capture_output=True, creationflags=0x08000000)


@contextlib.contextmanager
def server(name, slots=2, context_pool=204800, no_spec=False, draft=4):
    with socket.socket() as connection:
        if connection.connect_ex(('127.0.0.1', 18081)) == 0:
            raise RuntimeError('Benchmark port 18081 is already in use.')
    before = b.gpu()
    args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(b.ROOT / 'Start-Bonsai.ps1'), '-EnableGpu', '-Mtp',
            '-ParallelRequests', str(slots), '-TotalContext', str(context_pool),
            '-CacheTypeK', 'q8_0', '-CacheTypeV', 'q8_0', '-Port', '18081',
            '-BatchSize', '2048', '-MicroBatchSize', '512', '-DraftTokens', str(draft)]
    if no_spec:
        args.append('-DisableSpeculation')
    with (b.RUN / f'{name}.stdout.log').open('w') as out, (b.RUN / f'{name}.stderr.log').open('w') as err:
        process = subprocess.Popen(args, stdout=out, stderr=err, creationflags=0x08000000)
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError(f'{name} failed to start; see its stderr log.')
                try:
                    if b.api('/health', timeout=2).get('status') == 'ok':
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                raise TimeoutError('Model startup timed out.')
            props = b.api('/props')
            b.save({'kind': 'profile_capacity', 'mode': name, 'packing': 'PQ2_0',
                    'cache_k': 'q8_0', 'cache_v': 'q8_0', 'batch': 2048, 'ubatch': 512,
                    'slots': props['total_slots'],
                    'context_pool': props['default_generation_settings']['n_ctx'],
                    'unified_kv': True,
                    'mtp_model': True, 'draft_tokens': 0 if no_spec else draft,
                    'speculation': props['default_generation_settings']['params'].get('speculative.types'),
                    'gpu_before': before, 'gpu_loaded': b.gpu()})
            yield
        finally:
            stop_owned()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
            time.sleep(2)
