#!/usr/bin/env python3
"""Resolve and fetch actual Arch ARM Omarchy packages; never claim runtime support.

Run on the scoped Arch builder so version comparison and signature verification
use libalpm and its trusted keyrings. No package installation or user HOME writes.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.omarchy_packages import (NAME, ResolutionError, installed_records, libalpm_compare,
                                    parse_database, resolve)

SHA256 = re.compile(r'[0-9a-f]{64}')


def relative(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Missing locked input path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value:
        raise ValueError('Locked input path escapes the cache')
    return value


def https(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password \
            or parsed.query or parsed.fragment:
        raise ValueError('Locked artifact URL must be plain HTTPS')


def load_lock(path):
    lock = json.loads(Path(path).read_text())
    if lock.get('schema_version') != 1 or lock.get('architecture') != 'aarch64':
        raise ValueError('Unsupported Omarchy package lock')
    requested = lock.get('requested')
    if not isinstance(requested, list) or not requested or any(
            not isinstance(p, str) or not NAME.fullmatch(p) for p in requested):
        raise ValueError('Invalid original package requests')
    if len(requested) != len(set(requested)) or len(requested) != lock['scope_counts']['package_requests'] \
            or lock['profiles'].get('full') != requested:
        raise ValueError('Original package scope was changed or dropped')
    relative(lock['package_list']['file'])
    if not SHA256.fullmatch(lock['package_list']['sha256']):
        raise ValueError('Original package list requires a SHA256 identity')
    names = set()
    for repo in lock['repositories']:
        if not NAME.fullmatch(repo['name']) or repo['name'] in names:
            raise ValueError('Invalid or duplicate repository')
        names.add(repo['name'])
        relative(repo['database_file']); https(repo['database_url']); https(repo['package_base_url'])
        if not SHA256.fullmatch(repo['database_sha256']) or not 0 < repo['database_bytes'] <= 32 * 1024**2:
            raise ValueError('Repository requires a bounded SHA256 identity')
    if not names:
        raise ValueError('No locked repositories')
    source = lock['omarchy_source']
    if source['repo'] != 'omacom/omarchy' or not re.fullmatch('[0-9a-f]{40}', source['commit']):
        raise ValueError('Original Omarchy requires an immutable official source')
    relative(source['archive_file'])
    if source['archive_url'] != 'https://codeload.github.com/omacom/omarchy/tar.gz/' + source['commit'] \
            or not SHA256.fullmatch(source['archive_sha256']) \
            or not 0 < source['archive_bytes'] <= 256 * 1024**2:
        raise ValueError('Invalid original Omarchy archive identity')
    return lock


def verify_file(path, sha256, size=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or size is not None and path.stat().st_size != size:
        raise ValueError('Missing, redirected or wrong-size artifact: ' + path.name)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != sha256:
        raise ValueError('SHA256 mismatch: ' + path.name)


def load_installed(path):
    """Load a bounded, internally consistent ALPM snapshot; it authorizes no writes."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > 4 * 1024**2:
            raise ValueError('Invalid installed inventory file')
        raw = source.read(4 * 1024**2 + 1)
        after = os.fstat(source.fileno())
        if len(raw) > 4 * 1024**2 or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) \
                != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('Installed inventory changed while reading')
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {'schema_version', 'architecture', 'packages',
                                                   'package_list_sha256', 'metadata_sha256'} \
            or type(value['schema_version']) is not int or value['schema_version'] != 1 \
            or value['architecture'] != 'aarch64':
        raise ValueError('Invalid installed inventory schema')
    rows = installed_records(value['packages'])
    package_list = ''.join(name + ' ' + rows[name]['version'] + '\n' for name in sorted(rows)).encode()
    metadata = json.dumps(value['packages'], sort_keys=True, separators=(',', ':')).encode()
    if hashlib.sha256(package_list).hexdigest() != value['package_list_sha256'] \
            or hashlib.sha256(metadata).hexdigest() != value['metadata_sha256']:
        raise ValueError('Installed inventory identity mismatch')
    return value


def audit(lock, cache, *, profile='full', compare=None, installed=None):
    cache = Path(cache)
    source = cache / relative(lock['package_list']['file'])
    verify_file(source, lock['package_list']['sha256'])
    original = [line.split('#', 1)[0].strip() for line in source.read_text().splitlines()
                if line.split('#', 1)[0].strip()]
    if original != lock['requested'] or lock['profiles']['full'] != original:
        raise ValueError('Locked requests disagree with the original package list')
    if profile not in lock['profiles']:
        raise ValueError('Unknown explicit package profile')
    requested = lock['profiles'][profile]
    index, rejected = [], []
    for repo in lock['repositories']:
        path = cache / relative(repo['database_file'])
        verify_file(path, repo['database_sha256'], repo['database_bytes'])
        index.extend(parse_database(path.read_bytes(), repo['name'], repo['package_base_url'], rejected=rejected))
    try:
        packages = resolve(index, requested, preferences=lock.get('provider_preferences'), compare=compare,
                           installed=installed if installed is not None else ())
        unresolved = []
    except ResolutionError as error:
        packages, unresolved = error.selected, error.unresolved
    return {'schema_version': 1, 'profile': profile, 'architecture': 'aarch64',
            'status': 'unresolved' if unresolved else 'transaction-resolved',
            'ready_to_fetch': not unresolved, 'omarchy_support_complete': False,
            'transaction_mode': 'additions-only' if installed is not None else 'complete',
            'preserves_installed_versions': installed is not None,
            'requested': requested, 'original_request_count': len(original),
            'repositories': lock['repositories'], 'quarantined_metadata': rejected,
            'unresolved': unresolved, 'packages': packages,
            'download_bytes': sum(p['size_bytes'] for p in packages),
            'installed_bytes': sum(p['installed_bytes'] for p in packages),
            'evidence_boundary': 'Dependency transaction only; not installed or usable Omarchy.'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        response.close()
        raise ValueError('Redirect refused for locked artifact')


def ensure_inputs(lock, cache):
    cache = Path(cache)
    source = lock['omarchy_source']
    archive = cache / relative(source['archive_file'])
    if not archive.exists() and not archive.is_symlink():
        download(source['archive_url'], archive, size=source['archive_bytes'],
                 sha256=source['archive_sha256'], maximum=source['archive_bytes'])
    verify_file(archive, source['archive_sha256'], source['archive_bytes'])
    path = cache / relative(lock['package_list']['file'])
    if not path.exists() and not path.is_symlink():
        member_name = 'omarchy-' + source['commit'] + '/install/omarchy-base.packages'
        with tarfile.open(archive, 'r:gz') as reader:
            matches = [m for m in reader if m.name == member_name]
            if len(matches) != 1 or not matches[0].isfile() or not 0 < matches[0].size <= 64 * 1024:
                raise ValueError('Missing or unsafe original package list in source archive')
            data = reader.extractfile(matches[0]).read()
        if hashlib.sha256(data).hexdigest() != lock['package_list']['sha256']:
            raise ValueError('Original package list disagrees with the source archive')
        if not path.resolve().is_relative_to(cache.resolve()):
            raise ValueError('Package list parent escapes the cache')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    verify_file(path, lock['package_list']['sha256'])
    for repo in lock['repositories']:
        path = cache / relative(repo['database_file'])
        if not path.exists() and not path.is_symlink():
            download(repo['database_url'], path, size=repo['database_bytes'],
                     sha256=repo['database_sha256'], maximum=repo['database_bytes'])
        verify_file(path, repo['database_sha256'], repo['database_bytes'])


def download(url, destination, *, size=None, sha256=None, maximum=64 * 1024):
    https(url)
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('Artifact destination is a symlink')
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'pacman/7.1.0'})
    opener = urllib.request.build_opener(NoRedirect())
    temporary = None
    try:
        with opener.open(request, timeout=30) as response, tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix='.omarchy-download-', delete=False) as output:
            temporary = Path(output.name)
            total = 0
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > maximum:
                    raise ValueError('Artifact download exceeds its budget')
                output.write(chunk)
        if sha256 is not None:
            verify_file(temporary, sha256, size)
        elif not 0 < total <= maximum:
            raise ValueError('Empty artifact download')
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch_transaction(transaction, cache, *, pacman_key='pacman-key', progress=None):
    if transaction.get('status') != 'transaction-resolved':
        raise ValueError('Cannot fetch an unresolved transaction')
    folder = Path(cache) / 'packages'
    folder.mkdir(parents=True, exist_ok=True)
    packages = transaction['packages']
    missing_bytes = 0
    for package in packages:
        filename = relative(package['filename'])
        if '/' in filename:
            raise ValueError('Package cache requires flat archive filenames')
        path = folder / filename
        if path.exists() or path.is_symlink():
            verify_file(path, package['sha256'], package['size_bytes'])
        else:
            missing_bytes += package['size_bytes']
    if shutil.disk_usage(folder).free < missing_bytes + 64 * 1024**2:
        raise ValueError('Insufficient space for the complete package transaction')
    receipts = []
    for number, package in enumerate(packages, 1):
        path = folder / package['filename']
        if not path.exists():
            download(package['url'], path, size=package['size_bytes'], sha256=package['sha256'],
                     maximum=package['size_bytes'])
        signature = path.with_name(path.name + '.sig')
        if signature.is_symlink():
            raise ValueError('Signature cache is a symlink')
        if package.get('signature'):
            if len(package['signature']) != 1:
                raise ValueError('Ambiguous package signature')
            data = base64.b64decode(package['signature'][0], validate=True)
            if not 0 < len(data) <= 64 * 1024:
                raise ValueError('Package signature exceeds its budget')
            signature.write_bytes(data)
        elif not signature.is_file():
            download(package['url'] + '.sig', signature)
        if not 0 < signature.stat().st_size <= 64 * 1024:
            raise ValueError('Invalid package signature file')
        result = subprocess.run([pacman_key, '--verify', str(signature), str(path)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError('Trusted package signature verification failed: ' + path.name)
        receipts.append({'filename': path.name, 'sha256': package['sha256'],
                         'signature_sha256': hashlib.sha256(signature.read_bytes()).hexdigest(),
                         'signature_status': 'verified', 'verifier': pacman_key})
        if progress:
            progress(number, len(packages), package['name'])
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=ROOT / 'third_party/omarchy.lock.json')
    parser.add_argument('--cache', type=Path, default=ROOT / 'build/omarchy-sources')
    parser.add_argument('--profile', default='full')
    parser.add_argument('--installed-inventory', type=Path,
                        help='actual ALPM snapshot; resolve additions without replacing installed packages')
    parser.add_argument('--vercmp', default='vercmp', help='actual libalpm version comparator executable')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true', help='fetch and verify the entire explicit profile')
    parser.add_argument('--pacman-key', default='pacman-key')
    arguments = parser.parse_args()
    try:
        lock = load_lock(arguments.lock)
        inventory = load_installed(arguments.installed_inventory) if arguments.installed_inventory else None
        ensure_inputs(lock, arguments.cache)
        result = audit(lock, arguments.cache, profile=arguments.profile,
                       installed=inventory['packages'] if inventory is not None else None,
                       compare=libalpm_compare(arguments.vercmp))
        if inventory is not None:
            result['installed_package_list_sha256'] = inventory['package_list_sha256']
            result['installed_metadata_sha256'] = inventory['metadata_sha256']
            result['installed_package_count'] = len(inventory['packages'])
        result['lock_sha256'] = hashlib.sha256(arguments.lock.read_bytes()).hexdigest()
        if arguments.fetch and result['ready_to_fetch']:
            result['verified_packages'] = fetch_transaction(
                result, arguments.cache, pacman_key=arguments.pacman_key,
                progress=lambda n, total, name: print(f'{n}/{total} verified {name}', flush=True))
            result['status'] = 'packages-verified'
            result['evidence_boundary'] = 'Package bytes and signatures only; not installed or usable Omarchy.'
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': result['status'], 'profile': result['profile'],
                          'requested': len(result['requested']), 'packages': len(result['packages']),
                          'unresolved': result['unresolved'], 'output': str(arguments.output)}))
        return 0 if result['ready_to_fetch'] else 2
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print('Omarchy preparation failed: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
