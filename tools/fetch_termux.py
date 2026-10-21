#!/usr/bin/env python3
"""Fetch pinned official companions; verify APK bytes and signer before receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SIGNER = 'b6da01480eefd5fbf2cd3771b8d1021ec791304bdd6c4bf41d3faabad48ee5e1'


def verify_bytes(path, artifact):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size != artifact['size_bytes']:
        raise ValueError('companion size/path mismatch')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(65536), b''):
            digest.update(chunk)
    if digest.hexdigest() != artifact['sha256']:
        raise ValueError('companion SHA-256 mismatch')


def load_lock(path):
    lock = json.loads(Path(path).read_text())
    if lock.get('schema_version') != 1 or len(lock.get('artifacts', [])) != 2:
        raise ValueError('companion lock schema invalid')
    expected = {'termux-v0.118.3-arm64-v8a.apk': ('com.termux', 'termux-app'),
                'termux-x11-20261005.apk': ('com.termux.x11', 'termux-x11')}
    seen = set()
    for artifact in lock['artifacts']:
        name = artifact.get('name')
        if name not in expected or name in seen:
            raise ValueError('unknown/duplicate companion')
        seen.add(name)
        package, repo = expected[name]
        url = urllib.parse.urlsplit(artifact.get('url', ''))
        if url.scheme != 'https' or url.netloc != 'github.com' \
                or not url.path.startswith(f'/termux/{repo}/releases/download/') \
                or artifact.get('package') != package or artifact.get('signer_sha256') != SIGNER:
            raise ValueError('companion source/signing identity invalid')
        if not re.fullmatch('[0-9a-f]{64}', artifact.get('sha256', '')) \
                or type(artifact.get('size_bytes')) is not int \
                or not 0 < artifact['size_bytes'] <= 64 * 1024 * 1024:
            raise ValueError('companion digest/size invalid')
    return lock


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        parsed = urllib.parse.urlsplit(new_url)
        if parsed.scheme != 'https' or parsed.hostname not in {
                'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}:
            raise ValueError('companion redirect escaped official HTTPS assets')
        return super().redirect_request(request, response, code, message, headers, new_url)


def fetch(artifact, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        verify_bytes(output, artifact)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.companion-', dir=output.parent)
    try:
        opener = urllib.request.build_opener(OfficialRedirects())
        request = urllib.request.Request(artifact['url'], headers={'User-Agent': 'LoopyDesktopCompanion/1'})
        start, total = time.monotonic(), 0
        with opener.open(request, timeout=20) as source, os.fdopen(fd, 'wb') as target:
            while True:
                if time.monotonic() - start > 180:
                    raise ValueError('companion download timeout')
                chunk = source.read1(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > artifact['size_bytes']:
                    raise ValueError('companion download size exceeded')
                target.write(chunk)
        verify_bytes(temporary, artifact)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_apk(path, artifact, sdk):
    tool = Path(sdk) / 'build-tools/36.1.0/apksigner'
    if not tool.is_file():
        raise ValueError('Android build-tools 36.1.0 apksigner required')
    env = os.environ.copy()
    # Bundled Android Studio JBR is used only in this child environment.
    java = Path('/Applications/Android Studio.app/Contents/jbr/Contents/Home')
    if java.is_dir() and not env.get('JAVA_HOME'):
        env['JAVA_HOME'] = str(java)
    output = subprocess.check_output([str(tool), 'verify', '--verbose', '--print-certs', str(path)],
                                     env=env, text=True, stderr=subprocess.STDOUT, timeout=30)
    signers = re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)', output)
    if [x.lower() for x in signers] != [artifact['signer_sha256']]:
        raise ValueError('companion APK signer mismatch')
    return {'verified': True, 'signer_sha256': signers[0].lower(), 'apksigner': '36.1.0'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=Path.home() / 'Library/Android/sdk')
    args = parser.parse_args()
    lock_path = ROOT / 'third_party/termux.lock.json'
    lock = load_lock(lock_path)
    destination = ROOT / 'build/termux/companions'
    results = []
    for artifact in lock['artifacts']:
        path = destination / artifact['name']
        fetch(artifact, path)
        signature = verify_apk(path, artifact, args.sdk)
        results.append({**artifact, 'path': str(path.relative_to(ROOT)), **signature})
        print(path)
    receipt = {'schema': 1, 'lock_sha256': hashlib.sha256(lock_path.read_bytes()).hexdigest(),
               'fetcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'artifacts': results, 'scope': 'verified downloaded companions; not installed or runtime accepted'}
    (destination / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
