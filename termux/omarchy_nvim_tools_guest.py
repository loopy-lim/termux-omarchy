"""Add only the seven pinned Neovim helper packages using existing trusted keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import uuid

MANIFEST_SHA = '73ead2f8f715eaf359b4f657177202b509d647608974589564187c38269125a7'
MANIFEST_BYTES = 2507
CONFIG = b'''[options]
Architecture = aarch64
DBPath = /var/lib/pacman
GPGDir = /etc/pacman.d/gnupg
SigLevel = Required TrustedOnly
LocalFileSigLevel = Required TrustedOnly
'''


def require(value, reason='nvim-tools-boundary'):
    if not value: raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(row):
    return (row.st_dev, row.st_ino, row.st_uid, row.st_mode, row.st_size,
            row.st_mtime_ns, row.st_ctime_ns, row.st_nlink)


def read(fd, name, maximum, *, owned=False):
    descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
    with os.fdopen(descriptor, 'rb') as source:
        row = os.fstat(source.fileno()); before = fingerprint(row)
        require(stat.S_ISREG(row.st_mode) and row.st_nlink == 1 and not row.st_mode & 0o022
                and row.st_size <= maximum and (not owned or row.st_uid == os.getuid()))
        data = source.read(maximum + 1)
        require(len(data) <= maximum and fingerprint(os.fstat(source.fileno())) == before)
        require(fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)) == before)
        return data


class Payload:
    def __init__(self, directory, *, owned=False):
        name, size, digest = 'nvim-tools-manifest.json', MANIFEST_BYTES, MANIFEST_SHA
        component = 'guest-neovim-tools'
        self.manifest_sha = digest
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            row = os.fstat(fd)
            require(not row.st_mode & 0o022 and (not owned or row.st_uid == os.getuid()))
            raw = read(fd, name, size, owned=owned)
            require(len(raw) == size and sha(raw) == digest, 'nvim-tools-manifest-sha')
            manifest = json.loads(raw)
            require(set(manifest) == {'schema', 'component', 'packages'} and manifest['schema'] == 1
                    and manifest['component'] == component)
            self.rows, self.data = manifest['packages'], {name: raw}
            require(isinstance(self.rows, list) and len(self.rows) == 7)
            names, files = set(), set()
            for entry in self.rows:
                require(isinstance(entry, dict) and set(entry) == {'name', 'version', 'file', 'bytes',
                    'sha256', 'signatureBytes', 'signatureSHA256'})
                require(isinstance(entry['name'], str) and re.fullmatch('[a-z0-9][a-z0-9+_.-]{0,63}', entry['name'])
                    and isinstance(entry['version'], str) and re.fullmatch('[a-zA-Z0-9:+_.-]{1,80}', entry['version'])
                    and isinstance(entry['file'], str) and re.fullmatch('[a-zA-Z0-9:+_.-]{1,180}[.]pkg[.]tar[.]xz', entry['file'])
                    and entry['name'] not in names and entry['file'] not in files)
                names.add(entry['name']); files.add(entry['file'])
                for name, size_key, hash_key, limit in ((entry['file'], 'bytes', 'sha256', 16777216),
                    (entry['file'] + '.sig', 'signatureBytes', 'signatureSHA256', 16384)):
                    require(type(entry[size_key]) is int and 1 <= entry[size_key] <= limit
                            and isinstance(entry[hash_key], str) and re.fullmatch('[a-f0-9]{64}', entry[hash_key]))
                    data = read(fd, name, entry[size_key], owned=owned)
                    require(len(data) == entry[size_key] and sha(data) == entry[hash_key], 'nvim-tools-package-sha')
                    self.data[name] = data
        finally:
            os.close(fd)


def command(argv):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          env=dict(os.environ, LANG='C', LC_ALL='C'), timeout=180)


def checked(runner, argv):
    result = runner(argv)
    require(result.returncode == 0 and len(result.stdout) + len(result.stderr) <= 262144,
            'nvim-tools-command-failed')
    return result.stdout


def package_rows(text):
    result = {}
    require(len(text) <= 131072)
    for line in text.splitlines():
        values = line.split(' ')
        require(len(values) == 2 and re.fullmatch('[a-z0-9][a-z0-9+_.-]{0,127}', values[0])
                and re.fullmatch('[a-zA-Z0-9:+_.-]{1,127}', values[1]) and values[0] not in result,
                'nvim-tools-package-list-invalid')
        result[values[0]] = values[1]
    require(len(result) <= 4096)
    return result


def trusted_signature(output):
    rows = [line.split() for line in output.splitlines() if line.startswith('[GNUPG:] ')]
    valid = [row[2] for row in rows if len(row) >= 3 and row[1] == 'VALIDSIG']
    reject = {'BADSIG', 'ERRSIG', 'REVKEYSIG', 'EXPKEYSIG', 'EXPSIG', 'KEYEXPIRED', 'SIGEXPIRED', 'NO_PUBKEY'}
    require(len(valid) == 1 and re.fullmatch('[A-F0-9]{40}', valid[0])
            and any(row[1] in ('TRUST_FULLY', 'TRUST_ULTIMATE') for row in rows if len(row) >= 2)
            and not any(row[1] in reject for row in rows if len(row) >= 2), 'nvim-tools-signature-untrusted')
    return valid[0]


def record(stage, row, previous=None):
    fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.transaction-' + uuid.uuid4().hex
    def current():
        try: return json.loads(read(fd, 'transaction.json', 16384))
        except FileNotFoundError: return None
    try:
        require(current() == previous, 'nvim-tools-journal-changed')
        name = temporary if previous is not None else 'transaction.json'
        with os.fdopen(os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd), 'wb') as output:
            output.write(json.dumps(row, sort_keys=True).encode()); output.flush(); os.fsync(output.fileno())
        if previous is not None:
            require(current() == previous, 'nvim-tools-journal-changed')
            os.replace(temporary, 'transaction.json', src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)


def execute(stage, *, install=False, before=None, runner=None):
    stage = Path(stage)
    runner = runner or command
    payload = Payload(stage)
    fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(read(fd, 'pacman.conf', 4096) == CONFIG, 'nvim-tools-config-changed')
        try: prior_transaction = json.loads(read(fd, 'transaction.json', 16384))
        except FileNotFoundError: prior_transaction = None
        if prior_transaction is not None:
            require(isinstance(prior_transaction, dict) and prior_transaction.get('schema') == 1
                    and prior_transaction.get('phase') == 'INSTALLED', 'nvim-tools-transaction-uncertain')
    finally: os.close(fd)
    expected = {r['name']: r['version'] for r in payload.rows}
    original = checked(runner, ['/usr/bin/pacman', '-Q']); prior = package_rows(original)
    require(all(name not in prior or prior[name] == version for name, version in expected.items()),
            'nvim-tools-existing-version-different')
    missing = {n: v for n, v in expected.items() if n not in prior}
    fingerprints = {}
    for row in payload.rows:
        path = str(stage / row['file'])
        status = checked(runner, ['/usr/bin/gpg', '--batch', '--no-auto-key-retrieve', '--no-auto-check-trustdb',
            '--lock-never', '--homedir', '/etc/pacman.d/gnupg', '--status-fd', '1', '--verify', path + '.sig', path])
        fingerprints[row['name']] = trusted_signature(status)
        require(package_rows(checked(runner, ['/usr/bin/pacman', '-Qp', path])) == {row['name']: row['version']},
                'nvim-tools-package-metadata-different')
    result = {'schema': 1, 'status': 'verified', 'guestUID': os.getuid(), 'missing': missing,
              'beforeSHA256': sha(original.encode()), 'beforePackageCount': len(prior),
              'signaturesVerified': len(payload.rows), 'signingFingerprints': fingerprints,
              'packageWrites': False}
    if prior_transaction is not None:
        require(not missing and isinstance(prior_transaction.get('newPackages'), dict)
                and all(expected.get(n) == v for n, v in prior_transaction['newPackages'].items()),
                'nvim-tools-transaction-uncertain')
    if not install or not missing: return result
    require(os.getuid() == 0 and before == result['beforeSHA256'], 'nvim-tools-package-review-changed')
    require(not os.path.lexists(stage / 'transaction.json'), 'nvim-tools-transaction-uncertain')
    files = [str(stage / r['file']) for r in payload.rows if r['name'] in missing]
    common = ['/usr/bin/pacman', '--config', str(stage / 'pacman.conf'), '--needed', '--noconfirm']
    require(package_rows(checked(runner, [*common, '-Up', '--print-format', '%n %v', *files])) == missing,
            'nvim-tools-plan-different')
    require(checked(runner, ['/usr/bin/pacman', '-Q']) == original, 'nvim-tools-package-review-changed')
    Payload(stage)
    fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: require(read(fd, 'pacman.conf', 4096) == CONFIG, 'nvim-tools-config-changed')
    finally: os.close(fd)
    row = {'schema': 1, 'phase': 'TRANSACTION_REQUESTED', 'beforeSHA256': result['beforeSHA256'], 'newPackages': missing}
    record(stage, row)
    try:
        checked(runner, [*common, '-U', '--logfile', str(stage / 'pacman.log'), *files])
        current_raw = checked(runner, ['/usr/bin/pacman', '-Q']); current = package_rows(current_raw)
        added = {n: v for n, v in current.items() if n not in prior}
        require(all(current.get(n) == v for n, v in prior.items()) and added == missing, 'nvim-tools-transaction-different')
        record(stage, dict(row, phase='INSTALLED', afterSHA256=sha(current_raw.encode())), row)
        return dict(result, status='installed', missing={}, added=added, packageWrites=True,
                    afterSHA256=sha(current_raw.encode()), afterPackageCount=len(current))
    except BaseException:
        record(stage, dict(row, phase='INSTALL_UNKNOWN'), row)
        raise ValueError('nvim-tools-transaction-uncertain') from None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=Path)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--before')
    args = parser.parse_args(argv)
    print(json.dumps(execute(args.stage, install=args.install, before=args.before), sort_keys=True))


if __name__ == '__main__': main()
