"""Real loopback SSH2 server/client evidence; fixture dependencies stay in build/."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / 'build/ssh-fixture/venv/bin/python'
SSH = Path('/usr/bin/ssh')


@unittest.skipUnless(PYTHON.is_file() and SSH.is_file(), 'workspace SSH fixture venv and OpenSSH required')
class SshFixtureTests(unittest.TestCase):
    def test_actual_openssh_exchange_and_foreign_commands_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            process = subprocess.Popen([str(PYTHON), str(ROOT / 'tools/ssh_test_server.py'), '--output',
                str(directory / 'server'), '--lifetime', '30'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                until = time.monotonic() + 5
                endpoint = directory / 'server/endpoint.json'
                while not endpoint.exists() and process.poll() is None and time.monotonic() < until:
                    time.sleep(.05)
                self.assertTrue(endpoint.is_file(), 'owned SSH fixture did not publish readiness')
                value = json.loads(endpoint.read_text())
                known = directory / 'known_hosts'
                known.write_text(value['known_hosts'])
                base = [str(SSH), '-T', '-F', 'none', '-o', 'StrictHostKeyChecking=yes', '-o',
                    f'UserKnownHostsFile={known}', '-o', 'BatchMode=yes', '-o', 'PreferredAuthentications=none',
                    '-o', 'ConnectTimeout=5', '-p', str(value['port']), '-l']
                foreign = subprocess.run(base + ['foreign', '--', '127.0.0.1', 'loopy-remote-witness'],
                                         capture_output=True, text=True, timeout=10)
                self.assertNotEqual(foreign.returncode, 0)
                arbitrary = subprocess.run(base + ['loopy-fixture', '--', '127.0.0.1', 'touch /tmp/forbidden'],
                                           capture_output=True, text=True, timeout=10)
                self.assertNotEqual(arbitrary.returncode, 0)
                witness = subprocess.run(base + ['loopy-fixture', '--', '127.0.0.1', 'loopy-remote-witness'],
                                         capture_output=True, text=True, timeout=10)
                self.assertEqual(witness.returncode, 0, witness.stderr)
                self.assertEqual(witness.stdout, 'LOOPY_REMOTE_SSH:' + value['nonce'] + '\n')
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            receipt = json.loads((directory / 'server/receipt.json').read_text())
            actual = [entry for entry in receipt['exchanges'] if entry.get('authenticated')]
            self.assertEqual(len(actual), 1)
            self.assertIn(actual[0]['host_key_type'], ('rsa-sha2-256', 'rsa-sha2-512'))
            self.assertTrue(receipt['listener_closed'])
            self.assertEqual(receipt['live_workers'], 0)
            self.assertFalse(receipt['host_private_key_persisted'])


if __name__ == '__main__':
    unittest.main()
