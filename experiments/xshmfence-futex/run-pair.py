#!/usr/bin/env python3
"""Drive two independently linked probe processes through 20 bounded handshakes.

Commands are JSON argv arrays (never shell strings); each must already include
LIBRARY wait|signal FILE before|after. The four-byte file must be initialized.
"""
import argparse
import json
import os
import selectors
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-command', required=True)
    parser.add_argument('--signal-command', required=True)
    parser.add_argument('--mode', choices=('before', 'after'), required=True)
    args = parser.parse_args()
    commands = [json.loads(args.wait_command), json.loads(args.signal_command)]
    for command, role in zip(commands, ('wait', 'signal')):
        if not isinstance(command, list) or not all(isinstance(s, str) and '\0' not in s for s in command) \
                or len(command) < 5 or command[-3] != role or command[-1] != args.mode:
            parser.error('command must end with LIBRARY ' + role + ' FILE ' + args.mode)
    children, pending = [], {}
    deadline = time.monotonic() + 60
    try:
        for command in commands:
            child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            children.append(child); pending[child] = bytearray()
        def expect(child, expected):
            data = pending[child]
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                while b'\n' not in data:
                    left = deadline - time.monotonic()
                    if left <= 0 or not selector.select(left): raise TimeoutError('probe deadline')
                    part = os.read(child.stdout.fileno(), 4096)
                    if not part: raise RuntimeError('probe exited before ' + expected)
                    data.extend(part)
                    if len(data) > 8192: raise RuntimeError('probe output bound')
            line, _, remainder = data.partition(b'\n'); data[:] = remainder
            if line.decode() != expected: raise RuntimeError('unexpected probe response: ' + line.decode())
        def go(child, cycle):
            child.stdin.write(('GO %d\n' % cycle).encode()); child.stdin.flush()
        waiter, sender = children
        for cycle in range(20):
            expect(waiter, 'READY %d' % cycle)
            go(sender, cycle); expect(sender, 'SENT %d' % cycle)
            if args.mode == 'before': go(waiter, cycle)
            expect(waiter, 'DONE %d' % cycle)
        for child in children:
            expect(child, 'PASS 20')
            if child.wait(timeout=max(.1, deadline - time.monotonic())):
                raise RuntimeError('probe failure')
        print(json.dumps({'status': 'PASS', 'mode': args.mode, 'cycles': 20}))
    finally:
        for child in children:
            if child.poll() is None: child.kill()
            child.wait()
            child.stdin.close(); child.stdout.close()


if __name__ == '__main__': main()
