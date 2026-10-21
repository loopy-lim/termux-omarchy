"""Packaging must reject drift between the shipped compositor, source and build evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OmarchyNativeInputsTests(unittest.TestCase):
    def test_packaging_rejects_unmatched_binary_source_receipt_and_links(self):
        module = ROOT / 'tools/omarchy_native_inputs.py'
        self.assertTrue(module.is_file(), 'SDK packaging has no native component provenance gate')
        spec = importlib.util.spec_from_file_location('native_inputs', module)
        checked = importlib.util.module_from_spec(spec); spec.loader.exec_module(checked)
        inputs = checked.checked_inputs(ROOT)
        self.assertIn(ROOT / 'android/assets/omarchy-native/Hyprland', inputs)
        self.assertIn(ROOT / 'build/omarchy-refresh-20261008/hyprland-source/src/pointer/PointerManager.cpp', inputs)
        self.assertIn(ROOT / 'android/assets/omarchy-native/aquamarine/libaquamarine.so.0.15.1', inputs)
        self.assertIn(ROOT / 'android/assets/omarchy-native/hyprtoolkit/libhyprtoolkit.so.0.6.0', inputs)
        self.assertIn(ROOT / 'build/omarchy-sources/hyprtoolkit-shm/src/window/IWaylandWindow.cpp', inputs)
        with tempfile.TemporaryDirectory(prefix='loopy-component-inputs-') as folder:
            root = Path(folder)
            for source in inputs:
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
            checked.checked_inputs(root)
            for relative in ('android/assets/omarchy-native/Hyprland',
                             'build/omarchy-refresh-20261008/hyprland-source/src/pointer/PointerManager.cpp',
                             'android/assets/omarchy-native/aquamarine/libaquamarine.so.0.15.1',
                             'android/assets/omarchy-native/aquamarine/provenance.json',
                             'build/omarchy-refresh-20261008/component-receipt.json',
                             'build/omarchy-refresh-20261008/reused/compile_commands.json',
                             'build/omarchy-refresh-20261008/reused/baseline-relink.json',
                             'third_party/omarchy.lock.json',
                             'android/assets/omarchy-native/hyprtoolkit/libhyprtoolkit.so.0.6.0',
                             'build/omarchy-sources/hyprtoolkit-shm/src/window/IWaylandWindow.cpp',
                             'third_party/hyprtoolkit.lock.json',
                             'build/deliverables/Omarchy-2026-10-07-arm64-cursor-resolve-reference/build-receipt.json'):
                path = root / relative; old = path.read_bytes(); path.write_bytes(old + b'changed')
                with self.assertRaises(ValueError, msg=relative): checked.checked_inputs(root)
                path.write_bytes(old)
            binary = root / 'android/assets/omarchy-native/Hyprland'; binary.unlink()
            binary.symlink_to(ROOT / 'android/assets/omarchy-native/Hyprland')
            with self.assertRaises(ValueError): checked.checked_inputs(root)


if __name__ == '__main__': unittest.main()
