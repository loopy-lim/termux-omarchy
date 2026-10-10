#!/usr/bin/env python3
"""Inspect source or explicitly install a completely prepared local asset set."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
from verify import read, validate

ROOT = Path(__file__).resolve().parents[1]


def check_android_sdk(text):
    if not re.fullmatch(r'[0-9]{1,3}', text.strip()) or int(text.strip()) < 28:
        raise ValueError('delivery-android-api-unsupported')


def installed_apk_path(text):
    rows = text.splitlines()
    if len(rows) != 1 or not re.fullmatch(r'package:/data/app/[A-Za-z0-9_~+=./-]+/base[.]apk', rows[0]):
        raise ValueError('delivery-input-apk-unavailable')
    path = Path(rows[0][8:])
    if '..' in path.parts:
        raise ValueError('delivery-input-apk-unavailable')
    return path


def native_ready(entries):
    import native
    from assets import verify_file, require
    tracer = -1
    if sys.platform in ('linux', 'android'):
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('TracerPid:'):
                tracer = int(line.split(':', 1)[1])
    native.validate_context(os.environ, system=sys.platform, machine=os.uname().machine,
                            uid=os.getuid(), executable=sys.executable, tracer=tracer)
    sdk = native.run(['/system/bin/getprop', 'ro.build.version.sdk'])
    check_android_sdk(sdk)
    require(stat.S_ISCHR(Path('/dev/kgsl-3d0').stat().st_mode)
            and os.access('/dev/kgsl-3d0', os.R_OK | os.W_OK), 'delivery-kgsl-unavailable')
    native.sources()
    installed = native.installed_packages()
    plan = native.plan(installed)
    require(not plan['missingPackages'] and all((native.PREFIX / name).is_file() for name in native.FILES),
            'delivery-native-prerequisites-missing')
    result = subprocess.run(['/system/bin/pm', 'path', 'com.termux.x11'],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=10, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 4096,
            'delivery-input-apk-unavailable')
    # Android legitimately hardlinks system-managed base.apk files. This
    # exception never applies to the owned installation assets.
    verify_file(installed_apk_path(result.stdout), entries['input/termux-x11.apk'],
                owned=False, platform_links=True)
    return native.HOME, native.PREFIX, installed


def apply_assets(directory, entries):
    from assets import require
    home, prefix, installed = native_ready(entries)
    # A fresh release cannot adopt a tablet's earlier private runtime or config.
    sys.path.insert(0, str(ROOT / 'runtime'))
    import omarchy_install as base
    import omarchy_setup as setup
    import omarchy_terminal_install as terminal
    existing = base.walk(home, '.local/share/loopy-omarchy')
    if existing is not None:
        os.close(existing)
        raise ValueError('delivery-existing-runtime-preserved')
    require(not base.existing_container(prefix), 'delivery-existing-container-preserved')
    launcher = prefix / 'bin/loopy-omarchy'
    require(not launcher.exists() and not launcher.is_symlink(), 'delivery-existing-launcher-preserved')
    import companion
    spec = json.loads(read(ROOT, 'manifests/companion.json'))
    companion.validate_spec(spec)
    require(spec['deb'] == entries['input/termux-x11-companion.deb'], 'delivery-companion-pin')
    companion.preflight(prefix, installed, spec)
    connection = companion.apply(directory, prefix, installed, spec)
    args = ['--bundle', str(directory / 'omarchy-base.bundle.tar'), '--sources', str(ROOT / 'runtime'),
            '--tools-dir', str(directory / 'tools'), '--proot-dir', str(directory / 'proot-guard'),
            '--input-dir', str(directory / 'korean-input')]
    for option, filename in (
        ('weston-payload', 'payload.tar'), ('weston-manifest', 'payload-manifest.json'),
        ('guest-payload', 'guest-payload.tar'), ('guest-manifest', 'guest-manifest.json'),
        ('workflow-payload', 'workflow-payload.tar'), ('workflow-manifest', 'workflow-manifest.json'),
        ('input-payload', 'input-config-payload.tar'), ('input-manifest', 'input-config-manifest.json')):
        args.extend(['--' + option, str(directory / filename)])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = setup.main(args)
    if code:
        row = json.loads(output.getvalue())
        reason = row.get('reason', '')
        raise ValueError(reason if re.fullmatch('[a-z0-9-]{1,64}', reason) else 'delivery-component-installation-failed')
    terminal.install(ROOT / 'runtime/omarchy_terminal.py', home, prefix)
    return {'schema': 1, 'status': 'installed-components', 'launcher': 'loopy-omarchy',
            'companion': connection,
            'runtimeStarted': False, 'fullFreshInstallVerified': False,
            'androidPermissionsGranted': False, 'deviceChangesRequested': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--check', action='store_true', help='verify source and list unmet prerequisites')
    operation.add_argument('--apply', action='store_true', help='explicit fresh installation from all reviewed assets')
    parser.add_argument('--bundle', type=Path, help='reserved for the reviewed future payload installer')
    parser.add_argument('--assets', type=Path, help='closed local set created by tools/prepare_distribution.py')
    args = parser.parse_args(argv)
    try:
        source = validate()
    except (OSError, ValueError, KeyError, TypeError, SyntaxError):
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': 'source-verification-failed',
                          'deviceChangesRequested': False}, sort_keys=True))
        return 1
    if args.assets is not None:
        try:
            from assets import catalog, verify_tree
            entries = catalog(ROOT)
            count = verify_tree(args.assets, entries)
            if args.apply:
                result = apply_assets(args.assets, entries)
            else:
                result = {'schema': 1, 'status': 'installation-assets-verified',
                          'filesVerified': count, 'fullFreshInstallVerified': False,
                          'deviceChangesRequested': False, 'androidPermissionsGranted': False}
            print(json.dumps(result, sort_keys=True))
            return 0
        except (OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as error:
            reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) else 'delivery-unavailable'
            print(json.dumps({'schema': 1, 'status': 'blocked', 'reason': reason,
                              'fullFreshInstallVerified': False}, sort_keys=True))
            return 2
    # No assets: preserve the source-alpha inspection and refusal contract.
    result = {'schema': 1, 'status': 'source-only-developer-alpha',
              'automaticInstallEnabled': False, 'binaryClosureComplete': False,
              'fullFreshInstallVerified': False, 'deviceChangesRequested': False,
              'source': {name: value for name, value in source.items()
                         if name not in ('missing', 'upstreamBundle')},
              'missing': source['missing'], 'upstreamBundle': source['upstreamBundle']}
    if args.apply:
        result.update(status='blocked', reason='binary-closure-unavailable')
    print(json.dumps(result, sort_keys=True))
    return 2 if args.apply else 0


if __name__ == '__main__':
    raise SystemExit(main())
