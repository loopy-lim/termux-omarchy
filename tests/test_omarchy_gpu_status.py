"""GPU status verdict boundaries with measured log-format fixtures; no device mutation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'termux/omarchy_gpu_status.py'

# Line formats from the measured docs; some numeric values are synthetic and
# flagged here. 306/306 with 584 frames/116.8 FPS and ok=3240 are measured
# (docs/research/2026-10-19-y900-graphics-acceleration-next.md, HANDOFF format in
# experiments/hyprland-export-fence/HANDOFF.md). Synthetic: X11_CPU's 294-frame/
# 58.8 FPS prefix (the 0/294 count itself is measured), avg_finish_us=0, and
# every number in HANDOFF_FALLBACK.
X11_GPU = 'LorieNative: 584 frames in 5.0 seconds = 116.8 FPS, 306/306 present copies offloaded to GPU\n'
X11_CPU = 'LorieNative: 294 frames in 5.0 seconds = 58.8 FPS, 0/294 present copies offloaded to GPU\n'
WESTON_GPU = 'Date: 2026-10-19 UTC\nOpenGL ES 3.2 renderer: Adreno (TM) 830\nexplicit sync: yes\n'
WESTON_CPU = 'Date: 2026-10-19 UTC\nOpenGL ES 3.2 renderer: llvmpipe (LLVM 19.1.7)\n'
HYPR_EXPORT = '[render] GPU presentation export ready\n'
HYPR_SHM = '[render] invalid modifiers; retaining SHM\n'
HANDOFF_OK = 'export fence-handoff: ok=3240 finish_fallback=0 avg_finish_us=0\n'
HANDOFF_FALLBACK = 'export fence-handoff: ok=8 finish_fallback=8 avg_finish_us=1980.5\n'
TOKEN = '22183934-c4fb-458d-bb99-0be8af3d7552'


def load():
    spec = importlib.util.spec_from_file_location('omarchy_gpu_status', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state_bytes(uid=None):
    return json.dumps({'schema': 1, 'uid': os.getuid() if uid is None else uid,
                       'token': TOKEN, 'display': ':40', 'phase': 'ready',
                       'width': 1920, 'height': 1280, 'requestedRefreshMhz': 120000}).encode()


def build(logs=(), ahb=None, state=None):
    """Create one fixture runtime root; ahb is a mapping of file name to bytes.

    Files get the device modes (0600/0700) explicitly so the shared group-write
    refusal cannot depend on the developer machine's umask.
    """
    directory = tempfile.TemporaryDirectory()
    root = Path(directory.name) / 'loopy-omarchy'
    (root / 'sessions' / TOKEN).mkdir(parents=True, mode=0o700)
    state_path = root / 'runtime-state.json'
    state_path.write_bytes(state if state is not None else state_bytes())
    state_path.chmod(0o600)
    for name, text in logs:
        log = root / 'sessions' / TOKEN / name
        log.write_text(text)
        log.chmod(0o600)
    if ahb is not None:
        (root / 'graphics-ahb').mkdir(mode=0o700)
        for name, content in ahb.items():
            member = root / 'graphics-ahb' / name
            member.write_bytes(content)
            member.chmod(0o600)
    return directory, root


class OmarchyGpuStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load()

    def collect(self, logs=(), ahb=None, state=None, fence=()):
        """fence entries are fence-log TEXTS; the tool contract takes paths."""
        directory, root = build(logs, ahb, state)
        self.addCleanup(directory.cleanup)
        paths = []
        for text in fence:
            path = root / 'fence.log'
            path.write_text(text)
            path.chmod(0o600)
            paths.append(path)
        return self.module.collect(root, paths)

    def test_measured_gpu_fixture_reports_every_hop_gpu_with_evidence(self):
        ahb = {'libvulkan_freedreno.so': b'\xff\x00ELF', 'icd.json': b'{"ICD":{}}'}
        ahb['selection.json'] = json.dumps({'schema': 1, 'sha256': {
            name: __import__('hashlib').sha256(content).hexdigest()
            for name, content in ahb.items()}}).encode()
        result = self.collect(
            logs=(('x11.log', X11_GPU), ('weston.log', WESTON_GPU), ('hyprland.log', HYPR_EXPORT)),
            ahb=ahb, fence=[HANDOFF_OK])
        self.assertEqual(result['summary'], 'gpu')
        self.assertEqual(result['hops']['present']['state'], 'gpu')
        self.assertEqual(result['hops']['present']['frames'], 584)
        self.assertEqual(result['hops']['present']['fps'], 116.8)
        self.assertEqual(result['hops']['weston']['state'], 'gpu')
        self.assertEqual(result['hops']['weston']['explicitSync'], 'yes')
        self.assertEqual(result['hops']['hyprland']['state'], 'gpu')
        self.assertEqual(result['hops']['hyprland']['avgFinishUs'], 0.0)
        self.assertEqual(result['hops']['ahb']['state'], 'installed')
        self.assertEqual(result['session']['display'], ':40')

    def test_measured_cpu_fallback_fixture_reports_cpu_without_guessing(self):
        result = self.collect(logs=(('x11.log', X11_CPU), ('weston.log', WESTON_CPU),
                                    ('hyprland.log', HYPR_SHM)))
        self.assertEqual(result['summary'], 'cpu')
        for name in ('present', 'weston', 'hyprland'):
            self.assertEqual(result['hops'][name]['state'], 'cpu', result['hops'][name])
        self.assertEqual(result['hops']['ahb']['state'], 'not-installed')
        self.assertTrue(result['hops']['present']['evidence'].startswith('0/294 present copies'))

    def test_partial_offload_and_glfinish_fallback_are_degraded(self):
        result = self.collect(
            logs=(('x11.log', X11_GPU.replace('306/306', '153/306')),
                  ('weston.log', WESTON_GPU), ('hyprland.log', '')),
            fence=[HANDOFF_FALLBACK])
        self.assertEqual(result['summary'], 'degraded')
        self.assertEqual(result['hops']['present']['state'], 'degraded')
        self.assertEqual(result['hops']['hyprland']['state'], 'degraded')
        self.assertEqual(result['hops']['hyprland']['avgFinishUs'], 1980.5)

    def test_absent_logs_stay_unknown_with_reasons(self):
        result = self.collect()
        self.assertEqual(result['summary'], 'unknown')
        for name in ('present', 'weston', 'hyprland'):
            self.assertEqual(result['hops'][name]['state'], 'unknown', name)
            self.assertTrue(result['hops'][name]['evidence'])
        self.assertEqual(result['hops']['ahb']['state'], 'not-installed')
        self.assertIn('x11.log', result['hops']['logReadErrors'])

    def test_symlinked_log_is_refused_and_foreign_state_never_adopted(self):
        directory, root = build(logs=(('x11.log', X11_GPU),))
        self.addCleanup(directory.cleanup)
        log = root / 'sessions' / TOKEN / 'x11.log'
        target = root / 'outside.txt'
        target.write_text(X11_GPU)
        log.unlink()
        log.symlink_to(target)
        result = self.module.collect(root)
        self.assertIn('x11.log', result['hops']['logReadErrors'])
        self.assertEqual(result['hops']['present']['state'], 'unknown')
        with mock.patch.object(self.module.os, 'getuid', return_value=os.getuid() + 1):
            foreign = self.module.collect(root)
        self.assertEqual(foreign['session'], None)
        # Ownership refusal may land on the unreadable or identity boundary; both refuse adoption.
        self.assertIn(foreign['refusal'], ('runtime-state identity refused',
                                           'runtime-state unreadable: gpu-status-file'))

    def test_ahb_digest_drift_is_integrity_error_and_binary_digest_uses_raw_bytes(self):
        result = self.collect(ahb={'libvulkan_freedreno.so': b'\xff\x00ELF', 'icd.json': b'{"ICD":{}}',
                                   'selection.json': json.dumps(
                                       {'schema': 1, 'sha256': {'libvulkan_freedreno.so': '00', 'icd.json': '01'}}).encode()})
        self.assertEqual(result['hops']['ahb']['state'], 'integrity-error')

    def test_corrupted_state_refuses_cleanly_without_raising(self):
        result = self.collect(state=b'{not json')
        self.assertEqual(result['session'], None)
        self.assertTrue(result['refusal'].startswith('runtime-state unreadable'))
        self.assertEqual(result['summary'], 'unknown')
        directory, root = build(state=b'{not json')
        self.addCleanup(directory.cleanup)
        refused = subprocess.run([sys.executable, str(TOOL), '--root', str(root), '--human'],
                                 capture_output=True, text=True, timeout=15)
        self.assertEqual(refused.returncode, 0, refused.stderr)
        self.assertIn('session: unavailable', refused.stdout)

    def test_default_fence_paths_follow_the_termux_layout(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        home = base / 'com.termux/files/home'
        root = home / '.local/share/loopy-omarchy'
        (root / 'sessions' / TOKEN).mkdir(parents=True, mode=0o700)
        state = root / 'runtime-state.json'
        state.write_bytes(state_bytes())
        state.chmod(0o600)
        rootfs_tmp = base / 'com.termux/files/usr/var/lib/proot-distro/containers/loopy-omarchy/rootfs/tmp'
        rootfs_tmp.mkdir(parents=True, mode=0o700)
        first = rootfs_tmp / 'loopy-export-profile.log'
        first.write_text(HANDOFF_OK)
        first.chmod(0o600)
        lr = base / 'com.termux/lr'
        lr.mkdir(parents=True, mode=0o700)
        second = lr / 'loopy-export-profile.log'
        second.write_text(HANDOFF_FALLBACK)
        second.chmod(0o600)
        paths = self.module.fence_paths(root)
        self.assertEqual([str(path) for path in paths], [str(first), str(second)])
        result = self.module.collect(root)
        self.assertEqual(result['hops']['hyprland']['state'], 'gpu')
        self.assertEqual(result['hops']['hyprland']['avgFinishUs'], 0.0)

    def test_main_json_and_human_output_are_bounded_and_report_exit_is_tool_success(self):
        directory, root = build(logs=(('x11.log', X11_GPU), ('weston.log', WESTON_GPU),
                                      ('hyprland.log', HYPR_EXPORT)))
        self.addCleanup(directory.cleanup)
        json_run = subprocess.run([sys.executable, str(TOOL), '--root', str(root)],
                                  capture_output=True, text=True, timeout=15)
        self.assertEqual(json_run.returncode, 0, json_run.stderr)
        report = json.loads(json_run.stdout)
        self.assertLessEqual(len(json_run.stdout.encode()), 16384)
        self.assertTrue(report['exitIsToolSuccessOnly'])
        human_run = subprocess.run([sys.executable, str(TOOL), '--root', str(root), '--human'],
                                   capture_output=True, text=True, timeout=15)
        self.assertEqual(human_run.returncode, 0)
        self.assertIn('summary: gpu', human_run.stdout)
        self.assertIn('performance acceptance', human_run.stdout)

    def test_missing_root_and_oversized_log_fail_with_public_reasons(self):
        missing = subprocess.run([sys.executable, str(TOOL), '--root', '/nonexistent-loopy'],
                                 capture_output=True, text=True, timeout=15)
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(json.loads(missing.stderr)['reason'], 'runtime root directory not found')
        directory, root = build()
        self.addCleanup(directory.cleanup)
        log = root / 'sessions' / TOKEN / 'x11.log'
        log.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
        result = self.module.collect(root)
        self.assertEqual(result['hops']['present']['state'], 'unknown')
        self.assertIn('x11.log', result['hops']['logReadErrors'])


if __name__ == '__main__':
    unittest.main()
