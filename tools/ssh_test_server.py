#!/usr/bin/env python3
"""Bounded, loopback-only SSH2 counterpart for an ordinary-app-UID client test.

Use the workspace test venv. This server never executes commands or opens a
host user shell. Authentication is deliberately none for one fixed fixture
identity, so it must remain on loopback and be removed after the VM test.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import signal
import socket
import threading
import time

import paramiko

IDENTITY = 'loopy-fixture'
COMMAND = b'loopy-remote-witness'


class FixtureRequest(paramiko.ServerInterface):
    def __init__(self):
        self.ready = threading.Event()
        self.command = None

    def check_auth_none(self, username):
        return paramiko.AUTH_SUCCESSFUL if username == IDENTITY else paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'none'

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == 'session' else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command):
        if command != COMMAND:
            return False
        self.command = command
        self.ready.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True


def serve_connection(connection, key, nonce, evidence, deadline):
    request = FixtureRequest()
    transport = paramiko.Transport(connection, disabled_algorithms={'keys': ['ssh-rsa'], 'pubkeys': ['ssh-rsa']})
    transport.banner_timeout = 5
    transport.auth_timeout = 5
    transport.handshake_timeout = 5
    try:
        transport.add_server_key(key)
        transport.start_server(server=request)
        channel = transport.accept(8)
        if channel is None or not request.ready.wait(max(0, min(8, deadline - time.monotonic()))):
            return
        if transport.get_username() != IDENTITY or not transport.is_authenticated():
            return
        response = ('LOOPY_REMOTE_SSH:' + nonce + '\n').encode()
        channel.sendall(response)
        channel.send_exit_status(0)
        channel.shutdown_write()
        channel.close()
        # ready is signalled inside the exec callback, before Paramiko sends its
        # ACK. Keep its transport thread alive for bounded peer completion;
        # channel.close() only closes our side of the SSH channel.
        transport.join(timeout=max(0, min(2, deadline - time.monotonic())))
        evidence.append({'username': IDENTITY, 'command': COMMAND.decode(), 'reply': response.decode().strip(),
                         'authenticated': True, 'ssh_protocol': transport.remote_version,
                         'host_key_type': transport.host_key_type})
    except (EOFError, OSError, paramiko.SSHException) as failure:
        evidence.append({'error': type(failure).__name__ + ': ' + str(failure)[:256]})
    finally:
        transport.close()
        connection.close()


def run(output: Path, lifetime: float, port: int = 0, nonce: str | None = None) -> dict:
    if not 0 <= port <= 65535 or not 1 <= lifetime <= 3600:
        raise ValueError('fixture port/lifetime out of range')
    nonce = nonce or secrets.token_hex(16)
    if not re.fullmatch(r'[0-9a-f]{32}', nonce):
        raise ValueError('fixture nonce must be 32 lowercase hex characters')
    if output.is_symlink() or output.exists() or any(parent.is_symlink() for parent in output.parents):
        raise ValueError('fixture output must be a new, non-symlink directory')
    output.mkdir(parents=True, mode=0o700)
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', port))
    listener.listen(4)
    listener.settimeout(.25)
    port = listener.getsockname()[1]
    public_key = key.get_name() + ' ' + key.get_base64()
    endpoint = {'schema': 1, 'host': '127.0.0.1', 'port': port, 'user': IDENTITY, 'nonce': nonce,
                'public_key': public_key, 'known_hosts': f'[127.0.0.1]:{port} {public_key}\n',
                'host_key_sha256': base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('='),
                'auth': 'none, fixture identity only', 'arbitrary_commands': False}
    (output / 'endpoint.json').write_text(json.dumps(endpoint, indent=2) + '\n')
    print(json.dumps(endpoint), flush=True)
    evidence, workers, stop = [], [], threading.Event()
    previous_term = signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    deadline = time.monotonic() + lifetime
    try:
        while not stop.is_set() and time.monotonic() < deadline:
            try:
                connection, address = listener.accept()
            except socket.timeout:
                continue
            if address[0] != '127.0.0.1' or len(workers) >= 8:
                connection.close()
                continue
            worker = threading.Thread(target=serve_connection, args=(connection, key, nonce, evidence, deadline), daemon=True)
            workers.append(worker)
            worker.start()
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        listener.close()
        for worker in workers:
            worker.join(10)
        receipt = {'schema': 1, 'observed_at': datetime.now(timezone.utc).isoformat(), 'endpoint': endpoint,
                   'exchanges': evidence, 'listener_closed': True, 'worker_count': len(workers),
                   'live_workers': sum(worker.is_alive() for worker in workers), 'paramiko_version': paramiko.__version__,
                   'not_packaged_in_apk': True, 'host_private_key_persisted': False}
        with (output / 'receipt.json').open('x') as target:
            json.dump(receipt, target, indent=2)
            target.write('\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lifetime', type=float, default=300)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--nonce')
    args = parser.parse_args()
    run(args.output.absolute(), args.lifetime, args.port, args.nonce)
