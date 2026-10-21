import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_device


class DeviceModelGateTests(unittest.TestCase):
    def collect(self, model, output):
        calls = []
        args = argparse.Namespace(serial='owned-device', adb=None, output=output,
                                  expect_manufacturer='lenovo', expect_model='TB522FU')

        def invoke(adb, serial, command, timeout=12):
            calls.append(command)
            values = {'ro.product.manufacturer': 'Lenovo', 'ro.product.model': model}
            text = 'device' if command == ['get-state'] else values.get(command[-1], '')
            return {'stdout': text + '\n', 'stderr': '', 'exit_code': 0,
                    'timed_out': False, 'duration_seconds': 0}

        with patch.object(audit_device, 'parse_args', return_value=args), \
                patch.object(audit_device, 'find_adb', return_value='adb'), \
                patch.object(audit_device, 'invoke', side_effect=invoke), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = audit_device.main()
        return result, calls

    def test_old_and_similarly_named_y900_abort_before_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            for model in ['TB570FU', 'TB522FU-extra', 'other TB522FU', 'Lenovo TB710FU']:
                output = Path(directory) / model.replace(' ', '-')
                result, calls = self.collect(model, output)
                self.assertEqual(result, 2)
                self.assertFalse(output.exists())
                self.assertEqual(calls, [['get-state'], ['shell', 'getprop', 'ro.product.manufacturer'],
                                         ['shell', 'getprop', 'ro.product.model']])

    def test_exact_model_collects_boot_gpu_evidence_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'audit'
            result, calls = self.collect('Lenovo TB522FU', output)
            self.assertEqual(result, 0)
            receipt = json.loads((output / 'receipt.json').read_text())
            self.assertEqual(receipt['model'], 'Lenovo TB522FU')
            for property_name in ['ro.boot.verifiedbootstate', 'ro.boot.flash.locked', 'ro.boot.vbmeta.device_state']:
                self.assertIn(['shell', 'getprop', property_name], calls)
            script = next(command[-1] for command in calls if '/dev/kgsl-3d0' in command[-1])
            self.assertIn('/dev/dri/renderD*', script)
            # The collector may inspect write access, but never opens or writes a node.
            forbidden = {'install', 'push', 'reboot', 'root', 'remount', 'setprop', 'su'}
            self.assertTrue(all(not (set(command) & forbidden) for command in calls))
            settings = [command for command in calls if command[:2] == ['shell', 'settings']]
            self.assertTrue(all(command[2] == 'get' for command in settings))
            self.assertIn('not normal app permissions', receipt['collection_context'])


if __name__ == '__main__':
    unittest.main()
