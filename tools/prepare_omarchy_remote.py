#!/usr/bin/env python3
"""Add signed Arch remote clients outside the immutable Omarchy image and HOME."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tools.omarchy_catalog import BUNDLE
from tools.omarchy_packages import parse_database, resolve
from tools.omarchy_rootfs import bundle, digest_file
from tools.prepare_omarchy import download, load_lock, verify_file
from tools.arch_vercmp import Comparator

SIGNER = '68B3537F39A313B3E574D06777193F152BDBE6A6'
REQUESTED = ('remmina', 'freerdp', 'libvncserver')
TRANSACTION = 'docs/validation/2026-10-06-omarchy/runtime-packages-verified.json'
ASSET = 'android/assets/omarchy-remote-client.tar.gz'
PROVENANCE = 'android/assets/omarchy-remote-client.provenance.json'
INVENTORY = 'android/assets/omarchy-remote-client.inventory'


def split_packages(candidate, installed):
    base = {p['name']: p for p in installed}
    added, reused = [], []
    for package in candidate:
        if package['name'] in base:
            if package != base[package['name']]:
                raise ValueError('Remote client would replace an installed package: ' + package['name'])
            reused.append(package)
        else:
            added.append(package)
    return added, reused


def plan(root=ROOT):
    root = Path(root); lock = load_lock(root / 'third_party/omarchy.lock.json')
    index = []
    for repo in lock['repositories']:
        path = root / 'build/omarchy-sources' / repo['database_file']
        verify_file(path, repo['database_sha256'], repo['database_bytes'])
        index.extend(parse_database(path.read_bytes(), repo['name'], repo['package_base_url'], rejected=[]))
    installed = json.loads((root / TRANSACTION).read_text())
    receipt = json.loads((root / BUNDLE / 'receipt.json').read_text())
    manifest = json.loads((root / BUNDLE / 'manifest.json').read_text())['files']
    if installed.get('status') != 'packages-verified' or installed.get('unresolved') \
            or installed.get('repositories') != lock['repositories'] \
            or installed.get('requested') != lock['profiles']['runtime'] \
            or receipt['package_names'] != sorted(p['name'] for p in installed['packages']):
        raise ValueError('Complete signed base package transaction differs')
    verify_file(root / BUNDLE / 'manifest.json', receipt['manifest_sha256'])
    with Comparator(root) as compare:
        candidate = resolve(index, REQUESTED, preferences=lock.get('provider_preferences'), compare=compare)
    added, reused = split_packages(candidate, installed['packages'])
    for package in reused:
        name = 'var/lib/pacman/local/' + package['name'] + '-' + package['version'] + '/desc'
        if name not in manifest or manifest[name]['kind'] != 'file':
            raise ValueError('Reused package is absent from the complete image: ' + package['name'])
    return {'schema': 1, 'requested': list(REQUESTED), 'added_packages': added, 'reused_packages': reused,
            'base_archive_sha256': receipt['archive_sha256'], 'base_manifest_sha256': receipt['manifest_sha256'],
            'base_package_count': len(installed['packages']), 'base_transaction_sha256': digest_file(root / TRANSACTION),
            'lock_sha256': digest_file(root / 'third_party/omarchy.lock.json')}


def verify_signatures(packages, cache, key, gpg='gpg'):
    receipts = []
    with tempfile.TemporaryDirectory(prefix='loopy-remote-gpg-') as temporary:
        home = Path(temporary); home.chmod(0o700)
        subprocess.run([gpg, '--batch', '--homedir', str(home), '--import', str(key)],
                       check=True, capture_output=True, timeout=10)
        for package in packages:
            path = cache / package['filename']
            verify_file(path, package['sha256'], package['size_bytes'])
            if len(package['signature']) != 1:
                raise ValueError('Missing unique pinned package signature')
            data = base64.b64decode(package['signature'][0], validate=True)
            signature = home / 'package.sig'; signature.write_bytes(data)
            result = subprocess.run([gpg, '--batch', '--homedir', str(home), '--status-fd', '1',
                                     '--verify', str(signature), str(path)],
                                    capture_output=True, text=True, timeout=10)
            valid = [line.split()[2:] for line in result.stdout.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
            if result.returncode or len(valid) != 1 or valid[0][0] != SIGNER:
                raise ValueError('Official Arch ARM signature differs: ' + package['name'])
            receipts.append({'name': package['name'], 'sha256': package['sha256'],
                             'signature_sha256': hashlib.sha256(data).hexdigest(), 'signer': SIGNER})
    return receipts


def inventory_text(receipt, files):
    lines = ['schema\t1', 'archive_sha256\t' + receipt['archive_sha256'],
             'archive_bytes\t' + str(receipt['archive_bytes']),
             'materialized_bytes\t' + str(receipt['materialized_bytes']),
             'entries\t' + str(receipt['entries']), 'base_archive_sha256\t' + receipt['base_archive_sha256']]
    for name, entry in sorted(files.items()):
        if any(c in name for c in '\t\n\r'):
            raise ValueError('Invalid remote inventory path')
        kind = entry['kind']
        if kind == 'file':
            lines.append('f\t' + name + '\t' + str(entry['mode']) + '\t' + entry['sha256'])
        elif kind == 'directory': lines.append('d\t' + name)
        elif kind == 'symlink': lines.append('l\t' + name + '\t' + entry['link'])
        else: raise ValueError('Unsupported remote inventory entry')
    return ('\n'.join(lines) + '\n').encode()


def prepare(root=ROOT, *, output=None, gpg='gpg', icons=None, publish=True):
    root = Path(root); result = plan(root)
    output = Path(output or root / 'build/omarchy-remote/client-bundle')
    cache = root / 'build/omarchy-remote/packages'; cache.mkdir(parents=True, exist_ok=True)
    for package in result['added_packages']:
        path = cache / package['filename']
        if not path.exists() and not path.is_symlink():
            download(package['url'], path, size=package['size_bytes'], sha256=package['sha256'], maximum=package['size_bytes'])
        verify_file(path, package['sha256'], package['size_bytes'])
    key = root / 'third_party/omarchy-remote-signing-key.asc'
    signatures = verify_signatures(result['added_packages'], cache, key, gpg)
    # Bind only RDP and VNC plugins. Optional credential/discovery/execution
    # plugins never enter the plugin directory used by this remote client.
    with tempfile.TemporaryDirectory(prefix='loopy-remote-plugins-') as temporary:
        extras = {}
        icon_receipt = None
        if icons is not None:
            from tools.omarchy_remote_icons import checked_icons, cache_pixels
            icon_root = Path(icons)
            icon_receipt = json.loads((icon_root / 'receipt.json').read_text())
            if icon_receipt['producer_sha256'] != digest_file(root / 'tools/omarchy_remote_icons.py') \
                    or icon_receipt['base_archive_sha256'] != result['base_archive_sha256'] \
                    or icon_receipt['base_manifest_sha256'] != result['base_manifest_sha256'] \
                    or set(icon_receipt['themes']) != {'Adwaita', 'hicolor'}:
                raise ValueError('Trusted raw icon producer or base source differs')
            for path in sorted((icon_root / 'share/icons').rglob('*')):
                if path.is_symlink(): raise ValueError('Trusted icon candidate redirects')
                if path.is_file():
                    extras['usr/' + str(path.relative_to(icon_root))] = path
            for theme in ('Adwaita', 'hicolor'):
                cache_pixels(extras['usr/share/icons/' + theme + '/icon-theme.cache'].read_bytes())
        remmina = next(p for p in result['added_packages'] if p['name'] == 'remmina')
        with tarfile.open(cache / remmina['filename']) as archive:
            for protocol in ('rdp', 'vnc'):
                name = 'remmina-plugin-' + protocol + '.so'
                member = archive.getmember('usr/lib/remmina/plugins/' + name)
                if not member.isfile() or not 0 < member.size < 4 * 1024**2:
                    raise ValueError('Bounded native remote plugin required')
                path = Path(temporary) / name; path.write_bytes(archive.extractfile(member).read()); path.chmod(0o755)
                extras['loopy-remmina/plugins/' + name] = path
        bundled = bundle(output, result['added_packages'], cache, extras=extras, compression='gzip',
                         max_bytes=64 * 1024**2, max_entries=5000)
    files = json.loads((output / 'manifest.json').read_text())['files']
    result.update(bundled, verified_signatures=signatures, signing_key_sha256=digest_file(key),
                  signing_key_fingerprint=SIGNER, signing_key_source='https://archlinuxarm.org/about/package-signing',
                  selected_plugins=['RDP', 'VNC'], package_scripts_executed=False,
                  physical_device=False, external_endpoint=False, omarchy_support_complete=False)
    if icon_receipt is not None:
        result['trusted_icons'] = icon_receipt
        checked_icons(icon_receipt, files, json.loads((root / BUNDLE / 'manifest.json').read_text())['files'])
    # App assets are derived inputs, with exact copies checked before each build.
    generated = {root / ASSET: (output / 'rootfs.tar.gz').read_bytes(),
                 root / PROVENANCE: (json.dumps(result, indent=2) + '\n').encode(),
                 root / INVENTORY: inventory_text(result, files)}
    for name in ('remote_connections.py', 'remote_desktop.py'):
        generated[root / 'android/assets/omarchy-bridge' / name] = (root / 'guest/desktop/usr/local/lib/loopy' / name).read_bytes()
    if not publish:
        (output / 'remote-provenance.json').write_bytes(generated[root / PROVENANCE])
        (output / 'remote-inventory').write_bytes(generated[root / INVENTORY])
        return result
    for destination, content in generated.items():
        if destination.is_symlink() or destination.exists() and destination.read_bytes() != content:
            raise ValueError('Existing remote asset differs; preserve it and choose a new version')
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream: stream.write(content)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--gpg', default='gpg')
    parser.add_argument('--icons', type=Path, help='Verified raw icon candidate directory')
    parser.add_argument('--no-publish', action='store_true', help='Leave canonical APK inputs unchanged')
    args = parser.parse_args()
    receipt = prepare(output=args.output, gpg=args.gpg, icons=args.icons, publish=not args.no_publish)
    print(json.dumps({'status': receipt['status'], 'packages_added': len(receipt['added_packages']),
                      'archive_bytes': receipt['archive_bytes'], 'archive_sha256': receipt['archive_sha256']}))
