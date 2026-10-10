"""Payload preparation must preserve reviewed bytes without installing a runtime."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


class PayloadPreparationTests(unittest.TestCase):
    def run_tool(self, *args, root=ROOT, env=None):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tools/prepare_runtime_payloads.py'),
                               '--source-root', str(root), *map(str, args)],
                              capture_output=True, text=True, timeout=15, env=env)

    def copied_tree(self, root):
        for name in ('runtime', 'profiles', 'guest', 'tools', 'installer', 'manifests'):
            shutil.copytree(ROOT / name, root / name)

    def test_check_prepares_current_sources_without_touching_home(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / 'preserve').write_bytes(b'unchanged')
            result = self.run_tool('--check', env=dict(os.environ, HOME=str(home)))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            row = json.loads(result.stdout)
            self.assertEqual(row['components']['workflow']['filesVerified'], 15)
            self.assertFalse(row['deviceChangesRequested'])
            self.assertFalse(row['binaryClosureComplete'])
            self.assertEqual(list(home.iterdir()), [home / 'preserve'])

    def test_outputs_are_reproducible_and_contain_current_public_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / 'first', Path(folder) / 'second'
            for target in (first, second):
                result = self.run_tool('--output', target)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(sorted(p.name for p in first.iterdir()),
                             ['guest-manifest.json', 'guest-payload.tar', 'input-config-manifest.json',
                              'input-config-payload.tar', 'preparation.json', 'workflow-manifest.json',
                              'workflow-payload.tar'])
            for path in first.iterdir():
                self.assertEqual(path.read_bytes(), (second / path.name).read_bytes())
            manifest = json.loads((first / 'workflow-manifest.json').read_text())
            with tarfile.open(first / 'workflow-payload.tar') as archive:
                members = archive.getmembers()
                self.assertEqual(len(members), 15)
                self.assertTrue(all(m.isfile() and m.mode == 0o600 and m.uid == m.gid == m.mtime == 0
                                    and m.uname == m.gname == '' for m in members))
                binding = 'home/omarchy/.local/share/loopy-omarchy-profile/bindings.lua'
                self.assertEqual(archive.extractfile('guest/' + binding).read(),
                                 (ROOT / 'profiles/bindings.lua').read_bytes())
                for member in members:
                    data = archive.extractfile(member).read()
                    self.assertEqual(hashlib.sha256(data).hexdigest(),
                                     manifest['files'][member.name.removeprefix('guest/')]['sha256'])

    def test_changed_source_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'source', Path(folder) / 'output'
            self.copied_tree(root)
            (root / 'profiles/zshrc').write_text('unexpected replacement\n')
            result = self.run_tool('--output', output, root=root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'preparation-source-hash')
            self.assertFalse(output.exists())

    def test_symlink_source_is_rejected_even_with_identical_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'source', Path(folder) / 'output'
            self.copied_tree(root)
            source = root / 'profiles/zshrc'
            source.rename(root / 'held')
            source.symlink_to(root / 'held')
            result = self.run_tool('--output', output, root=root)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'output'
            output.mkdir()
            (output / 'preserve').write_bytes(b'kept')
            result = self.run_tool('--output', output)
            self.assertEqual(result.returncode, 1)
            self.assertEqual((output / 'preserve').read_bytes(), b'kept')
            self.assertEqual(list(output.iterdir()), [output / 'preserve'])

    def test_output_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            target, output = Path(folder) / 'target', Path(folder) / 'output'
            target.mkdir()
            output.symlink_to(target, target_is_directory=True)
            result = self.run_tool('--output', output)
            self.assertEqual(result.returncode, 1)
            self.assertTrue(output.is_symlink())
            self.assertEqual(list(target.iterdir()), [])

    def test_changed_expected_payload_is_rejected_without_repinning(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'source', Path(folder) / 'output'
            self.copied_tree(root)
            path = root / 'manifests/runtime-build.json'
            manifest = json.loads(path.read_text())
            manifest['components']['workflow']['artifacts']['workflow-payload.tar']['sha256'] = '0' * 64
            path.write_text(json.dumps(manifest))
            result = self.run_tool('--output', output, root=root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'preparation-output-hash')
            self.assertFalse(output.exists())

    def test_wrong_weston_package_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            package, output = Path(folder) / 'weston.deb', Path(folder) / 'output'
            package.write_bytes(b'untrusted package')
            result = self.run_tool('--weston-deb', package, '--output', output)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'preparation-weston-deb-hash')
            self.assertFalse(output.exists())

    def test_failed_output_write_does_not_publish_a_completion_receipt(self):
        import prepare_runtime_payloads
        ordinary_open = os.open
        def failed_open(name, *args, **kwargs):
            if name == 'workflow-payload.tar':
                raise OSError('synthetic full disk')
            return ordinary_open(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'prepared'
            with patch.object(prepare_runtime_payloads.os, 'open', failed_open), self.assertRaises(OSError):
                prepare_runtime_payloads.write_output(output, {'workflow-payload.tar': b'payload'}, {'status': 'payloads-prepared'})
            self.assertFalse((output / 'preparation.json').exists())


class WestonArchiveBoundaryTests(unittest.TestCase):
    def package(self, members):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:xz', format=tarfile.USTAR_FORMAT) as archive:
            for name, content, link in members:
                row = tarfile.TarInfo(name)
                if link is not None:
                    row.type, row.linkname = tarfile.SYMTYPE, link
                else:
                    row.size = len(content)
                archive.addfile(row, None if link is not None else io.BytesIO(content))
        result = b'!<arch>\n'
        for name, content in (('debian-binary', b'2.0\n'), ('control.tar.xz', b'control'),
                              ('data.tar.xz', data.getvalue())):
            header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(content):<10}`\n'.encode()
            result += header + content + (b'\n' if len(content) % 2 else b'')
        return result

    def test_materializes_only_pinned_regular_package_members(self):
        from prepare_runtime_weston import weston_files
        data = b'fixture-weston\n'
        expected = {'bin/weston': {'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o700}}
        package = self.package([('./data/data/com.termux/files/usr/bin/weston', data, None)])
        self.assertEqual(weston_files(package, expected), {'bin/weston': (data, 0o700)})

    def test_archive_traversal_links_duplicates_and_extra_members_are_rejected(self):
        from prepare_runtime_weston import weston_files
        data = b'fixture-weston\n'
        expected = {'bin/weston': {'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o700}}
        ordinary = ('./data/data/com.termux/files/usr/bin/weston', data, None)
        cases = [
            [('./data/data/com.termux/files/usr/../escape', data, None)],
            [('./data/data/com.termux/files/usr/bin/weston', b'', '/etc/passwd')],
            [ordinary, ordinary],
            [ordinary, ('./data/data/com.termux/files/usr/extra', data, None)],
            [('./data/data/com.termux/files/usr/bin/weston', b'changed', None)],
        ]
        for members in cases:
            with self.subTest(members=members), self.assertRaises(ValueError):
                weston_files(self.package(members), expected)

    def test_truncated_ar_package_is_rejected(self):
        from prepare_runtime_weston import weston_files
        with self.assertRaises(ValueError):
            weston_files(b'!<arch>\nmissing-header', {})


if __name__ == '__main__':
    unittest.main()
