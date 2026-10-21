"""Clipboard event revisions must survive equal-content round trips."""

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "guest/desktop/usr/local/lib/loopy/desktop_clipboard.py"
spec = importlib.util.spec_from_file_location("desktop_clipboard_recurrence", SOURCE)
clip = importlib.util.module_from_spec(spec)
previous_bytecode = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    spec.loader.exec_module(clip)
finally:
    sys.dont_write_bytecode = previous_bytecode


class Pipe:
    def __init__(self):
        self.data, self.closed = b"", False
    def write(self, data):
        self.data += data
    def close(self):
        self.closed = True


class Process:
    def __init__(self, stdout=None):
        self.stdin, self.stdout, self.stopped, self.terminations = Pipe(), stdout, False, 0
    def poll(self):
        return 0 if self.stopped else None
    def terminate(self):
        self.terminations += 1
        self.stopped = True
    def wait(self, timeout=None):
        return 0


class ClipboardRecurrenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.android, self.guest = self.directory / "clip-android-token", self.directory / "clip-guest-token"

    def test_linux_a_after_android_b_replaces_the_old_a_record(self):
        clip.publish(self.guest, b"A")
        self.android.write_bytes(b"B")
        stdin = type("Stdin", (), {"buffer": io.BytesIO(b"A")})()
        with self.guest.open("rb") as old_record, patch.object(clip, "paths", return_value=(self.android, self.guest)), \
             patch.object(clip.sys, "stdin", stdin), patch.dict(os.environ, {"CLIPBOARD_STATE": "data"}):
            clip.export()
            self.assertNotEqual(os.fstat(old_record.fileno()).st_ino, self.guest.stat().st_ino)
        self.assertEqual(self.guest.read_bytes(), b"A")

    def test_android_a_after_linux_b_reimports_and_coalesces_only_identical_revisions(self):
        self.android.write_bytes(b"A")
        owners, processes, directory, android = [], [], self.directory, self.android
        class Events:
            def __iter__(self):
                yield "y\t" + str(directory) + "\t" + android.name + ".new\n"
                owners[0].stopped = True  # Linux B replaced the original wl-copy selection owner.
                temporary = directory / ".android-new"
                temporary.write_bytes(b"A")
                temporary.replace(android)
                yield "y\t" + str(directory) + "\t" + android.name + "\n"
                yield "y\t" + str(directory) + "\t" + android.name + "\n"
            def close(self):
                pass
        def popen(argv, **kwargs):
            process = Process(Events() if argv[0] == "/bin/busybox" else None)
            processes.append(process)
            if argv[0] == "wl-copy":
                owners.append(process)
            return process
        with patch.object(clip, "paths", return_value=(self.android, self.guest)), \
             patch.object(clip.subprocess, "Popen", side_effect=popen), patch.object(clip.signal, "signal"):
            clip.watch()
        self.assertEqual([owner.stdin.data for owner in owners], [b"A", b"A"])
        self.assertTrue(all(owner.stdin.closed for owner in owners))
        self.assertTrue(all(process.stopped for process in processes))

    def test_initial_nil_never_clears_android_and_explicit_clear_stays_a_new_event(self):
        with patch.object(clip, "paths", return_value=(self.android, self.guest)):
            for android_exists in (False, True):
                if android_exists:
                    self.android.write_bytes(b"Android text")
                with patch.dict(os.environ, {"CLIPBOARD_STATE": "nil"}):
                    clip.export()
                self.assertFalse(self.guest.exists())
            clip.publish(self.guest, b"A")
            with patch.dict(os.environ, {"CLIPBOARD_STATE": "sensitive"}):
                clip.export()
            self.assertEqual(self.guest.read_bytes(), b"A")
            with patch.dict(os.environ, {"CLIPBOARD_STATE": "clear"}):
                clip.export()
            self.assertEqual(self.guest.read_bytes(), b"")
            self.assertFalse(clip.publish(self.guest, b"\xff"))
            self.assertFalse(clip.publish(self.guest, b"bad\0text"))
            self.assertEqual(self.guest.read_bytes(), b"")

    def test_replacement_does_not_terminate_live_prior_selection_owner(self):
        self.android.write_bytes(b"A")
        owners, observed = [], []
        directory, android = self.directory, self.android
        class Events:
            def __iter__(self):
                temporary = directory / ".android-b"
                temporary.write_bytes(b"B")
                temporary.replace(android)
                yield "y\t" + str(directory) + "\t" + android.name + "\n"
                observed.append((len(owners), owners[0].terminations))
            def close(self):
                pass
        def popen(argv, **kwargs):
            process = Process(Events() if argv[0] == "/bin/busybox" else None)
            if argv[0] == "wl-copy":
                owners.append(process)
            return process
        with patch.object(clip, "paths", return_value=(self.android, self.guest)), \
             patch.object(clip.subprocess, "Popen", side_effect=popen), patch.object(clip.signal, "signal"):
            clip.watch()
        self.assertEqual(observed, [(2, 0)])
        self.assertEqual([owner.stdin.data for owner in owners], [b"A", b"B"])
        self.assertTrue(all(owner.stopped for owner in owners))

    def test_live_owner_cap_preserves_selection_then_retries_after_reap(self):
        self.android.write_bytes(b"A")
        owners, observed = [], []
        directory, android = self.directory, self.android
        class Events:
            def __iter__(self):
                for value in b"BCDEFGHI":
                    temporary = directory / ".android-next"
                    temporary.write_bytes(bytes([value]))
                    temporary.replace(android)
                    yield "y\t" + str(directory) + "\t" + android.name + "\n"
                observed.append((len(owners), owners[-1].stdin.data, owners[-1].stopped))
                owners[0].stopped = True  # The compositor naturally released an old owner.
                yield "y\t" + str(directory) + "\t" + android.name + "\n"
                temporary = directory / ".android-clear"
                temporary.write_bytes(b"")
                temporary.replace(android)
                yield "y\t" + str(directory) + "\t" + android.name + "\n"
            def close(self):
                pass
        def popen(argv, **kwargs):
            process = Process(Events() if argv[0] == "/bin/busybox" else None)
            if argv[0] == "wl-copy":
                owners.append(process)
            return process
        with patch.object(clip, "paths", return_value=(self.android, self.guest)), \
             patch.object(clip.subprocess, "Popen", side_effect=popen), patch.object(clip.signal, "signal"), \
             patch.object(clip.subprocess, "run") as clear, patch("builtins.print"):
            clip.watch()
        self.assertEqual(observed, [(8, b"H", False)])
        self.assertEqual([owner.stdin.data for owner in owners], [bytes([v]) for v in b"ABCDEFGHI"])
        clear.assert_called_once_with(["wl-copy", "--clear"], check=True, timeout=5)
        self.assertTrue(all(owner.stopped for owner in owners))


if __name__ == "__main__":
    unittest.main()
