"""Download verified artifacts and build the pinned Windows CUDA runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

SOURCE = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unpack(archive_path, target):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if not (target / member.filename).resolve().is_relative_to(target.resolve()):
                raise RuntimeError('Unsafe archive path: ' + member.filename)
        archive.extractall(target)


def download(item, root):
    dest = root / item['dir'] / item['name']
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        part = dest.with_name(dest.name + '.part')
        print('Downloading ' + item['name'], flush=True)
        subprocess.run(['curl.exe', '--location', '--fail', '--retry', '5',
                        '--continue-at', '-', '--output', str(part), item['url']], check=True)
        if part.stat().st_size != item['size'] or digest(part) != item['sha256']:
            raise RuntimeError('Download verification failed: ' + item['name'])
        part.replace(dest)
    print('Verifying ' + item['name'], flush=True)
    if dest.stat().st_size != item['size'] or digest(dest) != item['sha256']:
        raise RuntimeError('Verification failed: ' + str(dest))
    if item.get('extract_to'):
        unpack(dest, root / item['extract_to'])
    return {'file': str(dest), 'bytes': dest.stat().st_size,
            'sha256': item['sha256'], 'verified': True}


def copy_sources(root):
    if root == SOURCE:
        return
    names = ['Setup.ps1', 'Start-Bonsai.ps1', 'Stop-Bonsai.ps1',
             'Start-GPU-after-gaming.cmd', 'Preview-settings-no-GPU.cmd',
             'Stop-Bonsai.cmd', 'Switch-Bonsai.ps1',
             'OpenCode-Bonsai.ps1', 'OpenCode-Bonsai.cmd',
             'Install-OpenCode-Global.ps1', 'opencode.bonsai.example.json',
             'artifacts.json', 'README.md', 'LICENSE',
             'THIRD_PARTY.md']
    for name in names:
        shutil.copy2(SOURCE / name, root / name)
    for folder in ['tools', 'mtp/patches', 'docs']:
        shutil.copytree(SOURCE / folder, root / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def build_runtime(root, architecture, manifest):
    runtime = manifest['runtime']
    source = root / 'mtp/llama'
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        subprocess.run(['git', 'init', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'remote', 'add', 'origin', runtime['repository']], check=True)
        subprocess.run(['git', '-C', str(source), 'fetch', '--depth', '1', 'origin', runtime['revision']], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != runtime['revision']:
        raise RuntimeError('Existing runtime checkout is not at the pinned revision.')
    for item in runtime['patches']:
        patch = root / item['path']
        if digest(patch) != item['sha256']:
            raise RuntimeError('Patch checksum mismatch: ' + str(patch))
        base = ['git', '-C', str(source), 'apply']
        if subprocess.run(base + ['--check', str(patch)], capture_output=True).returncode == 0:
            subprocess.run(base + [str(patch)], check=True)
        elif subprocess.run(base + ['--reverse', '--check', str(patch)], capture_output=True).returncode:
            raise RuntimeError('Patch conflicts with runtime source: ' + str(patch))
    vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    vs = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
                                  'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                  '-property', 'installationPath'], text=True).strip()
    if not vs:
        raise RuntimeError('Visual Studio C++ Build Tools were not found.')
    devcmd = Path(vs) / 'Common7/Tools/VsDevCmd.bat'
    bundled = Path(vs) / 'Common7/IDE/CommonExtensions/Microsoft/CMake'
    cmake = shutil.which('cmake') or str(bundled / 'CMake/bin/cmake.exe')
    ninja = shutil.which('ninja') or str(bundled / 'Ninja/ninja.exe')
    build = source / 'build'
    commands = [
        '@echo off',
        subprocess.list2cmdline(['call', str(devcmd), '-arch=x64', '-host_arch=x64']),
        'if errorlevel 1 exit /b %errorlevel%',
        subprocess.list2cmdline([cmake, '-S', str(source), '-B', str(build), '-G', 'Ninja',
                                '-DCMAKE_MAKE_PROGRAM=' + ninja, '-DGGML_CUDA=ON',
                                '-DCMAKE_CUDA_ARCHITECTURES=' + str(architecture),
                                '-DCMAKE_BUILD_TYPE=Release', '-DLLAMA_BUILD_TESTS=OFF',
                                '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_APP=OFF',
                                '-DLLAMA_BUILD_UI=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF',
                                '-DLLAMA_OPENSSL=OFF']),
        'if errorlevel 1 exit /b %errorlevel%',
        subprocess.list2cmdline([cmake, '--build', str(build), '--parallel', '4', '--target', 'llama-server']),
        'exit /b %errorlevel%',
    ]
    script = root / 'mtp/build-native.cmd'
    script.write_text('\n'.join(commands) + '\n', encoding='utf-8')
    subprocess.run(['cmd.exe', '/d', '/c', str(script)], check=True)
    files = [{'file': str(p.relative_to(root)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
             for p in sorted((build / 'bin').iterdir()) if p.suffix in ('.dll', '.exe')]
    (root / 'mtp/build-verification.json').write_text(json.dumps({
        'source_revision': revision, 'cuda_architecture': architecture,
        'build_success': True, 'files': files}, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-dir', type=Path, default=SOURCE)
    parser.add_argument('--skip-build', action='store_true')
    parser.add_argument('--all-models', action='store_true')
    parser.add_argument('--abliterated', action='store_true')
    parser.add_argument('--cuda-architecture', type=int, default=86)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Python 3.11 or newer is required.')
    root = args.install_dir.resolve()
    # Generated batch files cannot safely represent these CMD expansion characters.
    if any(c in str(root) for c in '%!&|<>^\r\n'):
        parser.error('Install path contains unsupported shell characters.')
    root.mkdir(parents=True, exist_ok=True)
    copy_sources(root)
    manifest = json.loads((SOURCE / 'artifacts.json').read_text(encoding='utf-8'))
    verification = root / 'verification.json'
    records = json.loads(verification.read_text(encoding='utf-8-sig')) if verification.exists() else []
    by_path = {str(Path(r['file']).resolve()): r for r in records}
    for item in manifest['files']:
        selected = (item.get('default', False) or args.all_models or
                    (args.abliterated and item.get('flavor') == 'abliterated'))
        if not selected:
            continue
        record = download(item, root)
        by_path[record['file']] = record
        verification.write_text(json.dumps(list(by_path.values()), indent=2), encoding='utf-8')
    if not args.skip_build:
        build_runtime(root, args.cuda_architecture, manifest)
    print('Setup complete. Start-GPU-after-gaming.cmd starts GPU inference.')


if __name__ == '__main__':
    main()
