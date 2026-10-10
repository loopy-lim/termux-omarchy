#!/usr/bin/env python3
"""Check or explicitly prepare missing signed-APT native Termux prerequisites."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

PREFIX = Path('/data/data/com.termux/files/usr')
HOME = Path('/data/data/com.termux/files/home')
# Weston dependencies come from the pinned 14.0.2-3 .deb's control record.
WESTON_DEPENDENCIES = ('freerdp', 'libaml', 'libandroid-shmem', 'libcairo', 'libdrm',
    'libevdev', 'libglvnd', 'libseat', 'libwayland', 'libwebp', 'libxcb', 'libxcursor',
    'libxkbcommon', 'littlecms', 'pango', 'pipewire', 'xcb-util-cursor')
# Official Mesa builds include Zink; Freedreno's subpackage supplies the Turnip ICD.
PACKAGES = tuple(sorted(set(WESTON_DEPENDENCIES) | {'x11-repo', 'python', 'proot-distro',
    'xorg-xprop', 'xorg-xwininfo', 'xkeyboard-config', 'pulseaudio', 'libc++',
    'mesa', 'mesa-vulkan-icd-freedreno', 'vulkan-loader-generic'}))
FILES = ('bin/python3', 'bin/proot-distro', 'bin/xprop', 'bin/xwininfo',
    'bin/pulseaudio', 'bin/pactl', 'lib/libEGL_mesa.so', 'lib/libvulkan_freedreno.so',
    'share/vulkan/icd.d/freedreno_icd.aarch64.json')
APT_OPTIONS = ('-o', 'APT::Get::AllowUnauthenticated=false',
    '-o', 'Acquire::AllowInsecureRepositories=false',
    '-o', 'Acquire::AllowDowngradeToInsecureRepositories=false')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def validate_context(env, *, system, machine, uid, executable, tracer):
    require(system in ('linux', 'android') and machine == 'aarch64' and 10000 <= uid < 100000
            and env.get('PREFIX') == str(PREFIX) and env.get('HOME') == str(HOME)
            and re.fullmatch(re.escape(str(PREFIX)) + r'/bin/python(?:3(?:\.[0-9]+)?)?', executable)
            and tracer == 0, 'native-primary-termux-required')
    require(not any(env.get(key) for key in ('PD_CONTAINER', 'OMARCHY_PROOT', 'PROOT_ROOTFS',
            'PROOT_DISTRIBUTION', 'PROOT_DISTRO')), 'native-guest-shell-refused')


def supported_proot(value):
    return re.fullmatch(r'(?:5\.8(?:\.[0-9]+)?|5\.9\.0)(?:-[0-9]+)?', value) is not None


def plan(installed):
    version = installed.get('proot-distro')
    require(version is None or supported_proot(version), 'native-proot-version-unreviewed')
    return {'schema': 1, 'status': 'native-prerequisites-plan',
            'missingPackages': sorted(set(PACKAGES) - set(installed)),
            'fullFreshInstallVerified': False, 'androidPermissionsGranted': False,
            'signaturePolicy': 'existing-APT-keyring-required', 'packageUpgradesAllowed': False}


def check_solver(text, installed):
    require(len(text) <= 1048576, 'native-apt-output-too-large')
    added = set()
    for line in text.splitlines():
        require(not re.match(r'^(?:Remv|Purg)\s', line), 'native-apt-removal-refused')
        match = re.match(r'^Inst ([a-z0-9][a-z0-9+.:_-]*)(?:\s|$)', line)
        if match:
            name = match[1].split(':')[0]
            require(name not in installed and '[' not in line.split('(', 1)[0], 'native-apt-upgrade-refused')
            if name == 'proot-distro':
                version = re.match(r'^Inst proot-distro(?::aarch64)?\s+\(([^ ]+) ', line)
                require(version and supported_proot(version[1]), 'native-proot-version-unreviewed')
            added.add(name)
    return added


def check_apt_sources(text):
    active = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
    require(not re.search(r'(?:trusted|allow-insecure|allow-weak|allow-downgrade-to-insecure)\s*(?:=|:)\s*(?:yes|true|1)\b',
                          active, re.I), 'native-apt-insecure-source')


def sources():
    paths = [PREFIX / 'etc/apt/sources.list']
    directory = PREFIX / 'etc/apt/sources.list.d'
    require(not directory.is_symlink(), 'native-apt-source-filesystem')
    if directory.exists():
        paths.extend(sorted(p for p in directory.iterdir() if p.suffix in ('.list', '.sources')))
    found = False
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
        with os.fdopen(os.open(path, flags), 'r') as source:
            row = os.fstat(source.fileno())
            require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid() and row.st_nlink == 1
                    and not row.st_mode & 0o022 and row.st_size <= 1048576, 'native-apt-source-filesystem')
            text = source.read(1048577)
            require(len(text) <= 1048576, 'native-apt-source-filesystem')
        check_apt_sources(text)
        found = found or bool(re.search(r'^\s*(?:deb\s|Types:\s*deb)', text, re.M))
    require(found, 'native-apt-sources-unavailable')


def run(args, *, capture=True, timeout=30):
    env = {'HOME': str(HOME), 'PREFIX': str(PREFIX), 'TERMUX__HOME': str(HOME),
           'TERMUX__PREFIX': str(PREFIX), 'TERMUX_APP__PACKAGE_NAME': 'com.termux',
           'PATH': str(PREFIX / 'bin') + ':/system/bin', 'ANDROID_ROOT': '/system',
           'ANDROID_DATA': '/data', 'TMPDIR': str(PREFIX / 'tmp'), 'LANG': 'C.UTF-8',
           'DEBIAN_FRONTEND': 'noninteractive'}
    result = subprocess.run(args, shell=False, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    require(result.returncode == 0, 'native-command-failed')
    require(not capture or len(result.stdout) <= 1048576, 'native-command-output-too-large')
    return result.stdout if capture else ''


def installed_packages():
    text = run([str(PREFIX / 'bin/dpkg-query'), '-W', '-f=${binary:Package}\t${db:Status-Abbrev}\t${Version}\n'])
    installed = {}
    for line in text.splitlines():
        fields = line.split('\t')
        require(len(fields) == 3 and re.fullmatch(r'[a-z0-9][a-z0-9+._-]*(?::aarch64)?', fields[0]),
                'native-package-query')
        if fields[1] != 'ii ':
            continue
        require(re.fullmatch(r'[A-Za-z0-9:._+~-]+', fields[2]), 'native-package-query')
        installed[fields[0].split(':')[0]] = fields[2]
    return installed


def proot_candidate():
    text = run([str(PREFIX / 'bin/apt-cache'), 'policy', 'proot-distro'])
    versions = re.findall(r'^\s*Candidate:\s*(\S+)\s*$', text, re.M)
    require(len(versions) == 1 and supported_proot(versions[0]), 'native-proot-version-unreviewed')
    return versions[0]


def install_missing(names, installed):
    # Exact constraints keep *every* existing package at its current version,
    # including transitive dependencies. --no-upgrade alone does not do that.
    constraints = [name + '=' + version for name, version in sorted(installed.items())]
    requested = [name + '=' + proot_candidate() if name == 'proot-distro' else name for name in names]
    command = [str(PREFIX / 'bin/apt-get'), *APT_OPTIONS, '--no-upgrade', '--no-remove',
               '--no-install-recommends', 'install', *requested, *constraints]
    simulated = run([*command[:1], '--simulate', *command[1:]], timeout=120)
    added = check_solver(simulated, installed)
    require(set(names) <= added, 'native-apt-plan-incomplete')
    require(installed_packages() == installed, 'native-package-state-changed')
    run([*command[:1], '-y', *command[1:]], capture=False, timeout=900)
    after = installed_packages()
    require(all(after.get(name) == version for name, version in installed.items())
            and set(names) <= set(after), 'native-package-result-changed')
    return after


def apply(installed):
    plan(installed)
    sources()
    run([str(PREFIX / 'bin/apt-get'), *APT_OPTIONS, 'update'], capture=False, timeout=180)
    require(installed_packages() == installed, 'native-package-state-changed')
    if 'proot-distro' not in installed:
        proot_candidate()  # Refuse an unreviewed version before even installing x11-repo.
    if 'x11-repo' not in installed:
        installed = install_missing(['x11-repo'], installed)
        sources()
        run([str(PREFIX / 'bin/apt-get'), *APT_OPTIONS, 'update'], capture=False, timeout=180)
    missing = plan(installed)['missingPackages']
    if missing:
        installed = install_missing(missing, installed)
    require(not plan(installed)['missingPackages'], 'native-prerequisites-incomplete')
    require(all((PREFIX / name).is_file() for name in FILES), 'native-required-file-missing')
    return {'schema': 1, 'status': 'native-prerequisites-installed',
            'packagesVerified': len(PACKAGES), 'fullFreshInstallVerified': False,
            'androidPermissionsGranted': False, 'packageUpgradesAllowed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--check', action='store_true')
    operation.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        tracer = -1
        if sys.platform in ('linux', 'android'):
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith('TracerPid:'):
                    tracer = int(line.split(':', 1)[1])
        validate_context(os.environ, system=sys.platform, machine=os.uname().machine,
                         uid=os.getuid(), executable=sys.executable, tracer=tracer)
        from verify import validate
        validate()  # Source integrity before invoking APT or reading native package state.
        sources()
        installed = installed_packages()
        result = apply(installed) if args.apply else plan(installed)
        if args.check:
            result['missingFiles'] = [name for name in FILES if not (PREFIX / name).is_file()]
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch(r'(?:native|source)-[a-z-]+', str(error)) else 'native-unavailable'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason,
                          'fullFreshInstallVerified': False}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
