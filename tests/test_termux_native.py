"""Executable boundaries for the native Termux kit, without Android mutations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def cleanup_child(child):
    if child.poll() is None:
        child.kill()
    child.wait(timeout=3)


class NativeTermuxTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'termux/runtime.py').is_file(),
                        'native Termux runtime is not implemented')
        sys.path.insert(0, str(ROOT / 'termux'))
        self.addCleanup(sys.path.remove, str(ROOT / 'termux'))
        self.runtime = module('native_runtime', ROOT / 'termux/runtime.py')
        self.proc = module('native_processes', ROOT / 'termux/processes.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home'
        self.prefix = Path(self.temp.name) / 'usr'
        self.home.mkdir()
        (self.prefix / 'bin').mkdir(parents=True)
        self.owner = self.home / '.local/share/loopy-native'
        self.owner.mkdir(parents=True)
        self.session = self.runtime.Runtime(self.home, self.prefix)

    def executable(self, name, body):
        path = self.prefix / 'bin' / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o700)
        return path

    def test_arbitrary_action_and_non_uuid_request_cannot_execute(self):
        for action, request in [('shell', '693ed2ef-74d1-44b5-bc10-337f4719011d'),
                                ('start', '../../escape'), ('start', 'x' * 4096)]:
            with self.assertRaises(ValueError):
                self.runtime.validate_request(action, request)

    def test_result_preserves_nonce_identity_and_one_bounded_json_line(self):
        result = self.runtime.result('doctor', '693ed2ef-74d1-44b5-bc10-337f4719011d',
                                     'failed', ':20', reason='e' * 30000)
        encoded = self.runtime.encode_result(result)
        self.assertLessEqual(len(encoded.encode()), 16384)
        self.assertEqual(encoded.count('\n'), 0)
        self.assertEqual(json.loads(encoded)['request'], '693ed2ef-74d1-44b5-bc10-337f4719011d')
        self.assertEqual(json.loads(encoded)['uid'], os.getuid())

    def test_symlink_owner_directory_never_receives_runtime_writes(self):
        other = Path(self.temp.name) / 'other'
        other.mkdir()
        self.owner.rmdir()
        self.owner.symlink_to(other)
        with self.assertRaises(ValueError):
            self.runtime.Runtime(self.home, self.prefix)
        self.assertEqual(list(other.iterdir()), [])

    def test_proc_stat_parentheses_do_not_shift_start_time_identity(self):
        # After the comm closing parenthesis, state is field 3, starttime field 22.
        stat = '123 (worker (native)) S ' + ' '.join(['1', '123', *(['0'] * 16), '987654', '0'])
        parsed = self.proc.parse_stat(stat)
        self.assertEqual(parsed['pgid'], 123)
        self.assertEqual(parsed['starttime'], '987654')

    def test_changed_pid_start_time_is_not_owned_even_if_command_matches(self):
        old = {'pid': 123, 'pgid': 123, 'uid': os.getuid(), 'starttime': '100', 'command': ['python3', 'runtime.py']}
        now = dict(old, starttime='101')
        self.assertFalse(self.proc.same_process(old, now))
        self.assertFalse(self.proc.same_process(old, dict(old, uid=os.getuid() + 1)))
        self.assertFalse(self.proc.same_process(old, dict(old, command=['foreign'])))

    def test_timeout_terminates_only_spawned_child_group(self):
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)'],
                                    start_new_session=True)
        self.addCleanup(cleanup_child, sentinel)
        with self.assertRaisesRegex(ValueError, 'timeout'):
            self.proc.run_bounded([sys.executable, '-c', 'import time;time.sleep(20)'], timeout=.1)
        self.assertIsNone(sentinel.poll())
        sentinel.terminate()
        sentinel.wait(timeout=3)

    def test_excessive_child_output_is_rejected_instead_of_truncated_success(self):
        with self.assertRaisesRegex(ValueError, 'output|exit'):
            self.proc.run_bounded([sys.executable, '-c', 'print("x"*1000000)'], max_bytes=1024)

    def test_x_socket_presence_does_not_replace_real_display_and_wm_probe(self):
        self.executable('xdpyinfo', 'raise SystemExit(1)\n')
        self.executable('xprop', 'raise SystemExit(1)\n')
        self.assertEqual(self.session.readiness(':20'), (False, False))
        self.executable('xdpyinfo', 'print("name of display: :20")\n')
        self.executable('xprop', 'print("_NET_SUPPORTING_WM_CHECK: no such atom on any window")\n')
        self.assertEqual(self.session.readiness(':20'), (True, False))

    def test_verbose_visual_inventory_does_not_reject_verified_x_connection(self):
        self.executable('xdpyinfo', 'print("visual:"*20000)\n')
        self.executable('xprop', 'print("_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x123")\n')
        self.assertEqual(self.session.readiness(':20'), (True, True),
                         'unrelated visual inventory size rejected a real X/WM response')

    def test_unprepared_runtime_cannot_claim_start_ready(self):
        self.executable('termux-x11', 'raise SystemExit(7)\n')
        self.executable('i3', 'raise SystemExit(7)\n')
        response = self.session.start('693ed2ef-74d1-44b5-bc10-337f4719011d')
        self.assertEqual(response['status'], 'failed')
        self.assertFalse(response.get('xReady', False))

    def test_empty_stop_is_idempotent_and_does_not_signal_other_processes(self):
        one = self.session.stop('693ed2ef-74d1-44b5-bc10-337f4719011d')
        two = self.session.stop('2479ab71-aa85-47e9-8e4c-79bc9f7c2b2d')
        self.assertEqual(one['status'], 'stopped')
        self.assertEqual(two['status'], 'stopped')

    def test_marker_cannot_claim_an_unrelated_same_uid_process_group(self):
        foreign = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)'],
                                   start_new_session=True)
        self.addCleanup(cleanup_child, foreign)
        marker = {'schema': 1, 'uid': os.getuid(), 'token': '693ed2ef-74d1-44b5-bc10-337f4719011d',
                  'display': ':20', 'phase': 'ready', 'processes': [
                      {'pid': foreign.pid, 'pgid': foreign.pid, 'uid': os.getuid(),
                       'starttime': '100', 'command': [sys.executable, '-c', 'import time;time.sleep(20)']}]}
        self.session.path.write_text(json.dumps(marker))
        with self.assertRaisesRegex(ValueError, 'owner|command|identity'):
            self.session.stop('2479ab71-aa85-47e9-8e4c-79bc9f7c2b2d')
        self.assertIsNone(foreign.poll())
        foreign.terminate(); foreign.wait(timeout=3)

    def test_duplicate_owned_start_returns_existing_display_without_spawning(self):
        from unittest.mock import patch
        token = '693ed2ef-74d1-44b5-bc10-337f4719011d'
        record = {'pid': 123, 'pgid': 123, 'uid': os.getuid(), 'starttime': '100',
                  'command': [str(self.prefix / 'bin/python3'), str(self.owner / 'runtime.py'),
                              '_supervise', token, ':20']}
        children = [dict(record, pid=124, command=['termux-x11']),
                    dict(record, pid=125, command=['dbus-run-session'])]
        records = [record, *children]
        self.session.path.write_text(json.dumps({'schema': 1, 'uid': os.getuid(), 'token': token,
                                               'display': ':20', 'phase': 'ready', 'processes': records}))
        self.executable('xdpyinfo', 'print("name of display: :20")\n')
        self.executable('xprop', 'print("_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x123")\n')
        # /proc is absent on macOS; only kernel identity lookup is substituted.
        with patch.object(self.runtime, 'identity', side_effect=lambda pid: next(p for p in records if p['pid'] == pid)):
            response = self.session.start('2479ab71-aa85-47e9-8e4c-79bc9f7c2b2d')
        self.assertEqual(response['status'], 'ready')
        self.assertEqual(response['display'], ':20')
        self.assertEqual(response['evidence']['token'], token)
        self.assertEqual(response['evidence']['processes'][0]['pid'], 123)

    def test_surviving_supervisor_cannot_claim_dead_display_children_ready(self):
        from unittest.mock import patch
        token = '693ed2ef-74d1-44b5-bc10-337f4719011d'
        leader = {'pid': 123, 'pgid': 123, 'uid': os.getuid(), 'starttime': '100',
                  'command': [str(self.prefix / 'bin/python3'), str(self.owner / 'runtime.py'),
                              '_supervise', token, ':20']}
        self.session.path.write_text(json.dumps({'schema': 1, 'uid': os.getuid(), 'token': token,
                                               'display': ':20', 'phase': 'ready', 'processes': [leader]}))
        self.executable('xdpyinfo', 'print("name of display: :20")\n')
        self.executable('xprop', 'print("_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x123")\n')
        with patch.object(self.runtime, 'identity', return_value=leader):
            response = self.session.doctor('2479ab71-aa85-47e9-8e4c-79bc9f7c2b2d')
        self.assertEqual(response['status'], 'failed')

    def test_doctor_tree_reports_own_window_ids_without_user_titles(self):
        self.executable('i3-msg', '''import json
print(json.dumps({'id':1,'type':'root','nodes':[{'id':2,'type':'workspace','name':'1',
 'focused':False,'nodes':[{'id':3,'type':'con','window':123,'pid':456,
 'name':'private terminal title','focused':True}]}]}))
''')
        evidence = self.session.window_evidence(':20')
        self.assertEqual(evidence['windowCount'], 1)
        self.assertEqual(evidence['activeWindowId'], 123)
        self.assertEqual(evidence['activeWindowPid'], 456)
        self.assertEqual(evidence['workspace'], '1')
        self.assertNotIn('private terminal title', json.dumps(evidence))

    def test_window_pid_uses_real_x_property_when_i3_tree_omits_it(self):
        self.executable('i3-msg', 'print(\'{"type":"root","nodes":[{"type":"workspace","name":"1",'
                        '"nodes":[{"type":"con","window":123,"focused":true}]}]}\')\n')
        self.executable('xprop', 'print("_NET_WM_PID(CARDINAL) = 456")\n')
        evidence = self.session.window_evidence(':20')
        self.assertEqual(evidence['activeWindowPid'], 456)

    def test_dock_only_tree_cannot_claim_native_application_window_or_focus(self):
        tree = {'type': 'root', 'nodes': [{'type': 'output', 'nodes': [
            {'type': 'dockarea', 'nodes': [{'type': 'con', 'window': 901, 'pid': 902, 'focused': True}]}]}]}
        self.executable('i3-msg', 'print(' + repr(json.dumps(tree)) + ')\n')
        evidence = self.session.window_evidence(':20')
        self.assertEqual(evidence['windowCount'], 0, 'i3bar was counted as a native app')
        self.assertNotIn('activeWindowId', evidence, 'dock focus was reported as application input focus')

    def test_workspace_terminal_is_counted_without_i3bar_dock_window(self):
        tree = {'type': 'root', 'nodes': [{'type': 'output', 'nodes': [
            {'type': 'dockarea', 'nodes': [{'type': 'con', 'window': 901, 'focused': False}]},
            {'type': 'con', 'nodes': [{'type': 'workspace', 'name': '2', 'nodes': [
                {'type': 'con', 'window': 123, 'pid': 456, 'focused': True}]}]}]}]}
        self.executable('i3-msg', 'print(' + repr(json.dumps(tree)) + ')\n')
        evidence = self.session.window_evidence(':20')
        self.assertEqual(evidence['windowCount'], 1)
        self.assertEqual(evidence['activeWindowId'], 123)
        self.assertEqual(evidence['activeWindowPid'], 456)
        self.assertEqual(evidence['workspace'], '2')

    def terminal_process(self, proc, pid, ppid, command, uid=None, tty=0, start='12345'):
        directory = proc / str(pid); directory.mkdir(parents=True, exist_ok=True)
        owner = os.getuid() if uid is None else uid
        (directory / 'status').write_text(f'Uid:\t{owner}\t{owner}\t{owner}\t{owner}\n')
        fields = [str(ppid), str(pid), str(pid), str(tty), *(['0'] * 14), start, '0']
        (directory / 'stat').write_text(f'{pid} (native) S ' + ' '.join(fields))
        (directory / 'cmdline').write_bytes(b'\0'.join(x.encode() for x in command) + b'\0')
        return directory

    def active_terminal_tree(self):
        tree = {'type': 'root', 'nodes': [{'type': 'workspace', 'name': '1', 'nodes': [
            {'type': 'con', 'window': 123, 'pid': 456, 'focused': True}]}]}
        self.executable('i3-msg', 'print(' + repr(json.dumps(tree)) + ')\n')
        proc = Path(self.temp.name) / 'proc'; proc.mkdir()
        self.terminal_process(proc, 456, 400, [str(self.prefix / 'bin/xfce4-terminal'), '--disable-server'])
        return proc

    def test_mapped_terminal_without_shell_cannot_claim_input_ready(self):
        proc = self.active_terminal_tree()
        evidence = self.session.window_evidence(':20', proc=proc)
        self.assertEqual(evidence['windowCount'], 1)
        self.assertEqual(evidence['activeWindowPid'], 456)
        self.assertIs(evidence.get('activeTerminalShellReady'), False)

    def test_verified_same_uid_direct_bash_controlling_tty_is_input_ready(self):
        proc = self.active_terminal_tree()
        self.terminal_process(proc, 567, 456, [str(self.prefix / 'bin/bash'), '-l'], tty=34818)
        self.assertIs(self.session.window_evidence(':20', proc=proc)['activeTerminalShellReady'], True)

    def test_unverified_foreign_or_wrong_shell_child_cannot_claim_input_ready(self):
        proc = self.active_terminal_tree()
        cases = [([str(self.prefix / 'bin/bash'), '-l'], os.getuid() + 1, 456, 34818),
                 ([str(self.prefix / 'bin/bash'), '-l'], os.getuid(), 999, 34818),
                 (['/system/bin/sh'], os.getuid(), 456, 34818),
                 ([str(self.prefix / 'bin/bash'), '-c', 'script'], os.getuid(), 456, 34818),
                 ([str(self.prefix / 'bin/bash'), '-l'], os.getuid(), 456, 0)]
        for pid, (command, uid, ppid, tty) in enumerate(cases, 567):
            with self.subTest(command=command, uid=uid, ppid=ppid, tty=tty):
                self.terminal_process(proc, pid, ppid, command, uid=uid, tty=tty)
                self.assertIs(self.session.window_evidence(':20', proc=proc)['activeTerminalShellReady'], False)

    def test_foreign_window_owner_cannot_promote_same_uid_shell(self):
        proc = self.active_terminal_tree()
        self.terminal_process(proc, 456, 400, ['xfce4-terminal'], uid=os.getuid() + 1)
        self.terminal_process(proc, 567, 456, [str(self.prefix / 'bin/bash'), '-l'], tty=34818)
        self.assertIs(self.session.window_evidence(':20', proc=proc)['activeTerminalShellReady'], False)


    def test_owned_session_drops_foreign_startup_and_i3_socket_overrides(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'TERMUX_X11_XSTARTUP': 'foreign desktop',
                                     'I3SOCK': '/foreign/socket', 'XAUTHORITY': '/foreign/auth'}):
            session = self.runtime.Runtime(self.home, self.prefix)
        for key in ('TERMUX_X11_XSTARTUP', 'I3SOCK', 'XAUTHORITY'):
            self.assertFalse(key in session.env, f'foreign override retained: {key}')

    def test_native_gtk_environment_defaults_utf8_and_preserves_valid_explicit_locale(self):
        from unittest.mock import patch
        cases=[({'GDK_BACKEND':'wayland','LANG':'','LC_ALL':'invalid value','LC_CTYPE':'bad\nvalue'},
                'C.UTF-8',None,None),
               ({'GDK_BACKEND':'wayland','LANG':'ko_KR.UTF-8','LC_ALL':'C.UTF-8','LC_CTYPE':'ko_KR.UTF-8'},
                'ko_KR.UTF-8','C.UTF-8','ko_KR.UTF-8')]
        for environment,lang,all_value,ctype in cases:
            with patch.dict(os.environ,environment):
                session=self.runtime.Runtime(self.home,self.prefix)
            self.assertEqual(session.env.get('GDK_BACKEND'),'x11')
            self.assertEqual(session.env.get('LANG'),lang)
            self.assertEqual(session.env.get('LC_ALL'),all_value)
            self.assertEqual(session.env.get('LC_CTYPE'),ctype)

    def test_evidence_reports_actual_installed_package_versions(self):
        self.executable('dpkg-query', 'import sys\n'
                        'if "xterm" in sys.argv: raise SystemExit(1)\n'
                        'print("i3=4.25.1-1\\ntermux-x11-nightly=1.03.01-6")\n')
        evidence = self.session.evidence({'token': '693ed2ef-74d1-44b5-bc10-337f4719011d',
                                          'processes': []})
        self.assertEqual(evidence['packages']['i3'], '4.25.1-1')
        self.assertEqual(evidence['packages']['termux-x11-nightly'], '1.03.01-6')

    def test_missing_optional_terminal_provider_keeps_core_and_utf8_terminal_versions(self):
        self.executable('xfce4-terminal', 'raise SystemExit(0)\n')
        self.executable('aterm', 'raise SystemExit(0)\n')
        self.executable('dpkg-query', 'import sys\n'
                        'if "aterm" in sys.argv: raise SystemExit(1)\n'
                        'if "xfce4-terminal" in sys.argv: print("xfce4-terminal=1.1.5-1")\n'
                        'else: print("i3=4.25.1-1\\npython=3.13.7")\n')
        evidence=self.session.evidence({'token':'693ed2ef-74d1-44b5-bc10-337f4719011d','processes':[]})
        self.assertEqual(evidence['packages']['i3'],'4.25.1-1')
        self.assertEqual(evidence['packages']['xfce4-terminal'],'1.1.5-1')
        self.assertNotIn('aterm',evidence['packages'])

    def test_display_scan_exhaustion_has_bounded_total_time(self):
        from unittest.mock import patch
        with patch.object(self.session, 'readiness', return_value=(True, False)), \
                patch.object(self.runtime.time, 'monotonic', side_effect=[0, 0, 1, 4, 8]):
            with self.assertRaisesRegex(ValueError, 'display.*timeout'):
                self.session.choose_display()

    def test_installation_preserves_existing_user_i3_and_termux_preferences(self):
        install = module('native_install', ROOT / 'termux/install.py')
        i3 = self.home / '.config/i3/config'
        i3.parent.mkdir(parents=True)
        i3.write_text('user owns this config\n')
        props = self.home / '.termux/termux.properties'
        props.parent.mkdir()
        props.write_text('allow-external-apps=false\n')
        install.install(self.home, ROOT / 'termux')
        self.assertEqual(i3.read_text(), 'user owns this config\n')
        self.assertEqual(props.read_text(), 'allow-external-apps=false\n')
        self.assertTrue((self.owner / 'runtime.py').is_file())

    def test_installation_rejects_changed_helper_and_preserves_owned_i3_customization(self):
        install = module('native_install', ROOT / 'termux/install.py')
        install.install(self.home, ROOT / 'termux')
        config = self.owner / 'i3.config'
        config.write_text('my modified native config\n')
        install.install(self.home, ROOT / 'termux')
        self.assertEqual(config.read_text(), 'my modified native config\n')
        install.install(self.home, ROOT / 'termux')
        self.assertEqual(config.read_text(), 'my modified native config\n')
        helper = self.owner / 'runtime.py'
        helper.write_text('user edited helper\n')
        with self.assertRaisesRegex(ValueError, 'changed|modified'):
            install.install(self.home, ROOT / 'termux')
        self.assertEqual(helper.read_text(), 'user edited helper\n')

    def test_installation_updates_unedited_owned_config_to_current_version(self):
        import shutil
        install = module('native_install', ROOT / 'termux/install.py')
        source = Path(self.temp.name) / 'source'
        shutil.copytree(ROOT / 'termux', source)
        (source / 'i3.config').write_text('previous owned configuration\n')
        install.install(self.home, source)
        install.install(self.home, ROOT / 'termux')
        self.assertEqual((self.owner / 'i3.config').read_text(), (ROOT / 'termux/i3.config').read_text())

    def test_input_restore_preserves_edits_after_the_owned_preset(self):
        prefs = module('native_preferences', ROOT / 'termux/preferences.py')
        changes = prefs.restore_values({'fullscreen': 'false', 'pointerCapture': 'false'},
                                      {'fullscreen': 'true', 'pointerCapture': 'true'},
                                      {'fullscreen': 'false', 'pointerCapture': 'true'})
        self.assertEqual(changes, {'pointerCapture': 'false'})

    def test_generated_setup_is_self_contained_and_below_clipboard_bound(self):
        generator = module('native_generate', ROOT / 'termux/generate_setup.py')
        encoded = generator.generate(ROOT / 'termux')
        self.assertLessEqual(len(encoded.encode()), 65536)
        self.assertEqual(subprocess.run(['bash', '-n'], input=encoded, text=True,
                                        capture_output=True).returncode, 0)


class CompanionFetcherTests(unittest.TestCase):
    def test_wrong_cached_hash_never_republishes_companion(self):
        path = ROOT / 'tools/fetch_termux.py'
        self.assertTrue(path.is_file(), 'verified Termux companion fetcher is missing')
        fetch = module('termux_fetch', path)
        with tempfile.TemporaryDirectory() as temp:
            cached = Path(temp) / 'app.apk'
            cached.write_bytes(b'changed companion')
            with self.assertRaisesRegex(ValueError, 'SHA|size'):
                fetch.verify_bytes(cached, {'sha256': '0' * 64, 'size_bytes': 17})
            self.assertEqual(cached.read_bytes(), b'changed companion')


if __name__ == '__main__':
    unittest.main()
