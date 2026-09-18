import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('setup', ROOT / 'tools/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class ArtifactTests(unittest.TestCase):
    def test_checked_in_patch_hashes(self):
        manifest = json.loads((ROOT / 'artifacts.json').read_text())
        for patch in manifest['runtime']['patches']:
            self.assertEqual(setup.digest(ROOT / patch['path']), patch['sha256'])

    def test_archive_cannot_escape_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'runtime.zip'
            with zipfile.ZipFile(archive, 'w') as out:
                out.writestr('../escaped.txt', 'unexpected')
            with self.assertRaisesRegex(RuntimeError, 'Unsafe archive'):
                setup.unpack(archive, root / 'runtime')
            self.assertFalse((root / 'escaped.txt').exists())

    def test_corrupt_existing_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'model.gguf').write_bytes(b'bad')
            item = {'dir': '.', 'name': 'model.gguf', 'size': 3, 'sha256': '0' * 64}
            with self.assertRaisesRegex(RuntimeError, 'Verification failed'):
                setup.download(item, root)

    def test_verified_existing_artifact_can_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'runtime.zip'
            with zipfile.ZipFile(path, 'w') as out:
                out.writestr('runtime.dll', 'fixture')
            item = {'dir': '.', 'name': path.name, 'size': path.stat().st_size,
                    'sha256': setup.digest(path), 'extract_to': 'bin'}
            self.assertTrue(setup.download(item, root)['verified'])
            self.assertEqual((root / 'bin/runtime.dll').read_text(), 'fixture')


if __name__ == '__main__':
    unittest.main()
