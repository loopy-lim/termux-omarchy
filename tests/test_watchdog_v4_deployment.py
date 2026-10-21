"""Pinned ARM watchdog evidence and asset publication reject drift and redirects."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WatchdogV4DeploymentTests(unittest.TestCase):
    def module(self, name):
        path = ROOT / 'tools' / (name + '.py')
        self.assertTrue(path.is_file(), 'No guarded watchdog deployment: ' + name)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_pinned_candidate_closure_rejects_binary_source_receipt_and_extra_input(self):
        gate = self.module('omarchy_watchdog_v4_inputs')
        inputs = gate.candidate_inputs(ROOT)
        self.assertGreater(len(inputs), 1265)
        with tempfile.TemporaryDirectory(prefix='loopy-watchdog-inputs-') as folder:
            root = Path(folder)
            for source in inputs:
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
            gate.candidate_inputs(root)
            base = gate.CANDIDATE
            for relative in ('components/start-hyprland', 'build-receipt.json', 'process-regression.json', 'process-config-regression.json',
                             'candidate-source/start/src/main.cpp',
                             'reference-inputs/tools/build_omarchy_watchdog_v4.py',
                             'build-inputs/usr/lib/libc.so.6'):
                path = root / base / relative; old = path.read_bytes(); path.write_bytes(old + b'drift')
                with self.subTest(relative=relative), self.assertRaises(ValueError): gate.candidate_inputs(root)
                path.write_bytes(old)
            extra = root / base / 'unreviewed.hpp'; extra.write_text('EXTRA')
            with self.assertRaises(ValueError): gate.candidate_inputs(root)
            extra.unlink()
            binary = root / base / 'components/start-hyprland'; binary.unlink()
            binary.symlink_to(ROOT / base / 'components/start-hyprland')
            with self.assertRaises(ValueError): gate.candidate_inputs(root)

    def test_asset_publisher_and_consumer_preserve_existing_destinations(self):
        gate = self.module('omarchy_watchdog_v4_inputs'); publisher = self.module('publish_omarchy_watchdog_v4')
        inputs = gate.candidate_inputs(ROOT)
        with tempfile.TemporaryDirectory(prefix='loopy-watchdog-publish-') as folder:
            root = Path(folder)
            for source in inputs:
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
            for name in ('tools/publish_omarchy_watchdog_v4.py', 'tools/omarchy_watchdog_v4_inputs.py', 'tools/watchdog_elf.py'):
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / name, target)
            legacy = root / 'android/assets/omarchy-watchdog/start-hyprland'
            legacy.parent.mkdir(parents=True); legacy.write_text('PRESERVE_VERIFIED_V3')
            publisher.publish(root)
            self.assertEqual(legacy.read_text(), 'PRESERVE_VERIFIED_V3')
            shipped = gate.checked_inputs(root)
            binary = root / 'android/assets/omarchy-watchdog-v4/start-hyprland'
            self.assertIn(binary, shipped); before = binary.read_bytes()
            with self.assertRaises(ValueError): publisher.publish(root)
            self.assertEqual(binary.read_bytes(), before)
            record = root / 'android/assets/omarchy-watchdog-v4/provenance.json'
            original = record.read_bytes(); data = json.loads(original); data['binary_sha256'] = '0' * 64
            record.write_text(json.dumps(data))
            with self.assertRaises(ValueError): gate.checked_inputs(root)
            record.write_bytes(original)
            binary.write_bytes(before + b'drift')
            with self.assertRaises(ValueError): gate.checked_inputs(root)
            binary.write_bytes(before)
            assets = binary.parent; saved = assets.with_name('saved-watchdog'); assets.rename(saved)
            assets.symlink_to(saved, target_is_directory=True)
            with self.assertRaises(ValueError): gate.checked_inputs(root)


if __name__ == '__main__': unittest.main()
