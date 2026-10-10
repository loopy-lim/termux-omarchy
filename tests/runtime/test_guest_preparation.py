"""Guest adapter and Korean input payloads consume published source only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GuestPreparationTests(unittest.TestCase):
    def run_tool(self, *args, root=ROOT, env=None):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tools/prepare_runtime_payloads.py'),
                               '--source-root', str(root), *map(str, args)],
                              capture_output=True, text=True, timeout=15, env=env)

    def test_check_validates_guest_and_input_sources_without_inspecting_home(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / 'preserve').write_bytes(b'unchanged')
            result = self.run_tool('--check', env=dict(os.environ, HOME=str(home)))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            row = json.loads(result.stdout)
            self.assertEqual(row['components'].get('guest', {}).get('filesVerified'), 11)
            self.assertEqual(row['components'].get('inputConfig', {}).get('filesVerified'), 5)
            self.assertFalse(row['deviceChangesRequested'])
            self.assertEqual(list(home.iterdir()), [home / 'preserve'])

    def test_guest_payload_contains_current_public_worker_and_reviewed_qml(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'prepared'
            result = self.run_tool('--output', output)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with tarfile.open(output / 'guest-payload.tar') as archive:
                self.assertEqual(len(archive.getmembers()), 11)
                for target, source in (
                    ('usr/local/lib/loopy-omarchy/processes.py', 'runtime/processes.py'),
                    ('usr/local/lib/loopy-omarchy/omarchy_audio_guest.py', 'guest/omarchy_audio_guest.py'),
                    ('usr/share/omarchy/shell/plugins/panels/network/Panel.qml', 'guest/shell/plugins/panels/network/Panel.qml'),
                ):
                    self.assertEqual(archive.extractfile('guest/' + target).read(), (ROOT / source).read_bytes())
            with tarfile.open(output / 'input-config-payload.tar') as archive:
                self.assertEqual(len(archive.getmembers()), 5)
                gtk3 = archive.extractfile('guest/home/omarchy/.config/gtk-3.0/settings.ini').read()
                gtk4 = archive.extractfile('guest/home/omarchy/.config/gtk-4.0/settings.ini').read()
                self.assertEqual(gtk3, b'[Settings]\ngtk-im-module=fcitx\n')
                self.assertEqual(gtk4, gtk3)

    def test_changed_guest_qml_is_rejected_before_any_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'source', Path(folder) / 'output'
            for name in ('runtime', 'profiles', 'guest', 'tools', 'manifests'):
                shutil.copytree(ROOT / name, root / name)
            (root / 'guest/AndroidSettings.qml').write_text('unexpected source\n')
            result = self.run_tool('--output', output, root=root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'preparation-source-hash')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
