import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lenovo_input", ROOT / "tools/lenovo_input.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class FakeADB:
    serial = "physical-test"

    def __init__(self, settings=None, manufacturer="Lenovo", model="TB570FU", qemu=""):
        self.settings = dict(settings or {})
        self.props = {"ro.product.manufacturer": manufacturer, "ro.product.model": model,
                      "ro.kernel.qemu": qemu}
        self.calls = []
        self.before_write = None

    def shell(self, args):
        self.calls.append(tuple(args))
        if args[0] == "/system/bin/getprop":
            return self.props[args[1]] + "\n"
        assert args[:3] == ["/system/bin/settings", "--user", "0"]
        action = args[3]
        assert args[4] == "system"
        if action == "list":
            return "\n".join(f"{key}={value}" for key, value in self.settings.items())
        assert args[5] in tool.KEYS
        if self.before_write:
            self.before_write()
        if action == "put":
            self.settings[args[5]] = args[6]
        elif action == "delete":
            self.settings.pop(args[5], None)
        else:
            raise AssertionError(action)
        return ""

    def writes(self):
        return [call for call in self.calls if len(call) > 3 and call[3] in ("put", "delete")]


class LenovoInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.snapshot = Path(self.temp.name) / "original.json"

    def test_inspection_is_read_only_and_preserves_missing_vs_empty(self):
        adb = FakeADB({tool.KEYS[0]: "", tool.KEYS[1]: "1", "unrelated": "private"})
        report = tool.inspect(adb)
        self.assertTrue(report["supported"])
        self.assertEqual(report["settings"][tool.KEYS[0]], {"present": True, "value": ""})
        self.assertEqual(report["settings"][tool.KEYS[2]], {"present": False, "value": None})
        self.assertNotIn("unrelated", report["settings"])
        self.assertEqual(adb.writes(), [])

    def test_disable_persists_original_before_writes_and_restore_recovers_exact_values(self):
        original = {tool.KEYS[0]: "1", tool.KEYS[1]: "", tool.KEYS[2]: "0"}
        adb = FakeADB(original)
        def verify_snapshot():
            saved = json.loads(self.snapshot.read_text())
            self.assertEqual(saved["settings"][tool.KEYS[0]]["value"], "1")
            self.assertFalse(saved["settings"][tool.KEYS[3]]["present"])
        adb.before_write = verify_snapshot
        tool.disable(adb, self.snapshot)
        self.assertEqual(adb.settings, dict.fromkeys(tool.KEYS, "0"))
        tool.restore(adb, self.snapshot)
        self.assertEqual(adb.settings, original)

    def test_dry_run_reads_actual_state_but_never_writes_snapshot_or_device(self):
        adb = FakeADB({tool.KEYS[0]: "1"})
        tool.disable(adb, self.snapshot, dry_run=True)
        self.assertFalse(self.snapshot.exists())
        self.assertTrue(adb.calls)
        self.assertEqual(adb.writes(), [])

    def test_wrong_model_manufacturer_or_virtual_device_cannot_be_mutated(self):
        for adb in [FakeADB(model="TB371FU"), FakeADB(manufacturer="Google"), FakeADB(qemu="1")]:
            with self.subTest(props=adb.props):
                with self.assertRaises(tool.InputError):
                    tool.disable(adb, self.snapshot)
                self.assertEqual(adb.writes(), [])
                self.assertFalse(self.snapshot.exists())

    def test_restore_conflicts_are_preflighted_before_any_write(self):
        adb = FakeADB(dict.fromkeys(tool.KEYS, "1"))
        tool.disable(adb, self.snapshot)
        adb.calls.clear()
        adb.settings[tool.KEYS[-1]] = "changed-after-disable"
        with self.assertRaises(tool.InputError):
            tool.restore(adb, self.snapshot)
        self.assertEqual(adb.writes(), [])

    def test_snapshot_is_not_overwritten_and_foreign_device_is_refused(self):
        adb = FakeADB(dict.fromkeys(tool.KEYS, "1"))
        tool.disable(adb, self.snapshot)
        saved = self.snapshot.read_bytes()
        adb.calls.clear()
        with self.assertRaises(tool.InputError):
            tool.disable(adb, self.snapshot)
        self.assertEqual(saved, self.snapshot.read_bytes())
        self.assertEqual(adb.writes(), [])
        adb.serial = "other-physical-device"
        with self.assertRaises(tool.InputError):
            tool.restore(adb, self.snapshot)

    def test_partial_disable_failure_keeps_recoverable_snapshot(self):
        adb = FakeADB(dict.fromkeys(tool.KEYS, "1"))
        count = 0
        def fail_second_write():
            nonlocal count
            count += 1
            if count == 2:
                raise tool.InputError("device disconnected")
        adb.before_write = fail_second_write
        with self.assertRaises(tool.InputError):
            tool.disable(adb, self.snapshot)
        self.assertTrue(self.snapshot.is_file())
        adb.before_write = None
        tool.restore(adb, self.snapshot)
        self.assertEqual(adb.settings, dict.fromkeys(tool.KEYS, "1"))

    def test_restore_dry_run_and_already_restored_state_do_not_write(self):
        adb = FakeADB({tool.KEYS[0]: "1"})
        tool.disable(adb, self.snapshot)
        adb.calls.clear()
        tool.restore(adb, self.snapshot, dry_run=True)
        self.assertEqual(adb.writes(), [])
        tool.restore(adb, self.snapshot)
        adb.calls.clear()
        tool.restore(adb, self.snapshot)
        self.assertEqual(adb.writes(), [])

    def test_snapshot_publish_failure_prevents_device_mutation(self):
        adb = FakeADB({tool.KEYS[0]: "1"})
        with patch.object(tool.os, "link", side_effect=OSError("disk unavailable")):
            with self.assertRaises(tool.InputError):
                tool.disable(adb, self.snapshot)
        self.assertEqual(adb.writes(), [])
        self.assertFalse(self.snapshot.exists())
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_snapshot_cannot_expand_the_owned_setting_keys(self):
        adb = FakeADB({tool.KEYS[0]: "1"})
        tool.disable(adb, self.snapshot)
        snapshot = json.loads(self.snapshot.read_text())
        snapshot["settings"]["unrelated_setting"] = {"present": True, "value": "1"}
        self.snapshot.write_text(json.dumps(snapshot))
        adb.calls.clear()
        with self.assertRaises(tool.InputError):
            tool.restore(adb, self.snapshot)
        self.assertEqual(adb.writes(), [])

    def test_remote_shell_quoting_preserves_original_value_as_data(self):
        value = "original; $(touch /data/local/tmp/not-executed) 'x'"
        arguments = tool.SETTINGS + ["put", "system", tool.KEYS[0], value]
        with patch.object(tool.subprocess, "run", return_value=subprocess.CompletedProcess([],0,"","")) as run:
            tool.ADBRunner("chosen-serial").shell(arguments)
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["adb", "-s", "chosen-serial", "shell"])
        self.assertEqual(shlex.split(command[4]), arguments)
        self.assertNotIn("shell", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
