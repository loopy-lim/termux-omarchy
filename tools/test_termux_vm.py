#!/usr/bin/env python3
"""Prepare pinned Termux only on the explicitly owned emulator-5580; never runtime acceptance."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time
try:
    from tools.fetch_termux import load_lock, verify_apk, verify_bytes
except ModuleNotFoundError:
    from fetch_termux import load_lock, verify_apk, verify_bytes

ROOT = Path(__file__).resolve().parents[1]
SERIAL = 'emulator-5580'
PREFIX = '/data/data/com.termux/files/usr'
HOME = '/data/data/com.termux/files/home'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class VmPreparation:
    def __init__(self, sdk, vmroot, output):
        self.sdk, self.vmroot, self.output = sdk, vmroot.resolve(), output
        self.adb = sdk / 'platform-tools/adb'
        self.receipt = {'schema': 1, 'serial': SERIAL, 'owned_vm_root': str(self.vmroot),
                        'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'scope': 'owned disposable VM setup via run-as; not ordinary-app runtime acceptance',
                        'commands': [], 'mutations': [], 'runtime_accepted': False}
        self.output.mkdir(parents=True, exist_ok=False)

    def save(self):
        (self.output / 'receipt.json').write_text(json.dumps(self.receipt, indent=2) + '\n')

    def run(self, arguments, *, timeout=30, content=None, required=True, log=None):
        command = [str(self.adb), '-s', SERIAL, *arguments]
        record = {'argv': command, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if content is not None: record['stdin_sha256'] = hashlib.sha256(content).hexdigest()
        self.receipt['commands'].append(record)
        self.save()
        try:
            result = subprocess.run(command, input=content, capture_output=True, timeout=timeout)
            output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
            record.update({'exit': result.returncode, 'output': output[-32768:]})
            if log: (self.output / log).write_text(output)
            self.save()
            if required and result.returncode:
                raise RuntimeError(f'ADB command failed: {arguments[:4]}: {output[-1200:]}')
            return result.returncode, output
        except subprocess.TimeoutExpired as error:
            text = ((error.stdout or b'') + (error.stderr or b'')).decode('utf-8', errors='replace')
            record.update({'timeout': timeout, 'output': text[-32768:]})
            if log: (self.output / log).write_text(text)
            self.save()
            raise RuntimeError(f'ADB command timed out: {arguments[:4]}') from error

    def shell(self, arguments, **kwargs):
        return self.run(['shell', '-T', shlex.join(arguments)], **kwargs)

    def guard(self):
        if self.vmroot.name != 'loopy-desktop-vm.Atkn7Q' or not self.vmroot.is_dir():
            raise RuntimeError('Expected current explicitly owned Atkn7Q VM root')
        configs = list((self.vmroot / 'avd').glob('*.avd/config.ini'))
        if len(configs) != 1 or 'avd.name = Loopy_Feasibility' not in configs[0].read_text():
            raise RuntimeError('Owned AVD config does not match')
        _, name = self.run(['emu', 'avd', 'name'])
        _, properties = self.shell(['/system/bin/sh', '-c',
                                      'getprop ro.kernel.qemu; getprop sys.boot_completed; getprop ro.product.cpu.abi'])
        if name.splitlines()[0].strip() != 'Loopy_Feasibility' or properties.splitlines() != ['1', '1', 'arm64-v8a']:
            raise RuntimeError('Refusing non-owned, non-QEMU, unbooted or non-ARM64 target')
        self.receipt['guard'] = {'qemu': True, 'boot_completed': True, 'abi': 'arm64-v8a',
                                 'avd': 'Loopy_Feasibility', 'config_sha256': digest(configs[0])}
        self.save()

    def termux(self, *, content=None, command=None, timeout=30, log=None):
        environment = ['/system/bin/env', '-i', f'HOME={HOME}', f'PREFIX={PREFIX}',
                       f'TERMUX__PREFIX={PREFIX}', 'TERMUX_APK_RELEASE=GITHUB',
                       f'PATH={PREFIX}/bin:/system/bin', f'LD_PRELOAD={PREFIX}/lib/libtermux-exec.so',
                       f'TMPDIR={PREFIX}/tmp', f'SHELL={PREFIX}/bin/bash',
                       'TERM=xterm-256color', 'LANG=en_US.UTF-8']
        arguments = ['run-as', 'com.termux', *environment, f'{PREFIX}/bin/bash']
        arguments += ['-s'] if command is None else ['-c', command]
        return self.shell(arguments, content=content, timeout=timeout, log=log)

    def prepare(self):
        self.guard()
        lock_path = ROOT / 'third_party/termux.lock.json'
        lock = load_lock(lock_path)
        companions = ROOT / 'build/termux/companions'
        downloaded = json.loads((companions / 'receipt.json').read_text())
        if downloaded.get('lock_sha256') != digest(lock_path):
            raise RuntimeError('Downloaded companion receipt lock mismatch')
        self.receipt['companion_lock_sha256'] = digest(lock_path)
        self.receipt['companions'] = []
        for item in lock['artifacts']:
            path = companions / item['name']
            verify_bytes(path, item)
            signature = verify_apk(path, item, self.sdk)
            self.guard()
            _, previous = self.shell(['pm', 'path', item['package']], required=False)
            if previous.strip():
                raise RuntimeError('Fresh-VM preparation refuses an existing companion package')
            self.run(['install', str(path)], timeout=90)
            self.receipt['mutations'].append('installed ' + item['package'])
            _, package = self.shell(['dumpsys', 'package', item['package']])
            (self.output / (item['package'] + '-package.txt')).write_text(package)
            self.receipt['companions'].append({**item, **signature})
            self.save()
        self.guard()
        self.shell(['am', 'start', '-n', 'com.termux/.app.TermuxActivity'])
        deadline = time.monotonic() + 90
        while True:
            code, _ = self.shell(['run-as', 'com.termux', 'test', '-x', f'{PREFIX}/bin/bash'], required=False)
            if code == 0: break
            if time.monotonic() >= deadline: raise RuntimeError('Termux UI bootstrap did not create bash')
            time.sleep(1)
        self.receipt['bootstrap_ready'] = True
        self.guard()
        setup = ROOT / 'android/assets/loopy-termux-setup.sh'
        self.receipt['setup_sha256'] = digest(setup)
        self.receipt['setup_execution_context'] = 'run-as com.termux; ordinary app UID but runas_app SELinux'
        self.save()
        self.termux(command='id; cat /proc/self/attr/current; printf "\\n"; echo "$PREFIX"; echo "$HOME"',
                    log='setup-context.txt')
        self.termux(content=setup.read_bytes(), timeout=900, log='setup-install.txt')
        self.receipt['mutations'].append('native packages and owned Loopy runtime installed by setup script')
        self.termux(command="dpkg-query -W -f='${Package} ${Version}\\n'; cat \"$HOME/.local/share/loopy-native/installed.json\"",
                    log='native-packages.txt')
        self.receipt['setup_ready'] = True
        self.receipt['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()

    def upgrade(self):
        """Finish the latest managed helper and explicitly enable external commands in this VM only."""
        self.guard()
        lock_path = ROOT / 'third_party/termux.lock.json'
        lock = load_lock(lock_path)
        self.receipt['companion_lock_sha256'] = digest(lock_path)
        self.receipt['companions'] = []
        for item in lock['artifacts']:
            path = ROOT / 'build/termux/companions' / item['name']
            verify_bytes(path, item)
            signature = verify_apk(path, item, self.sdk)
            _, installed = self.shell(['pm', 'path', item['package']])
            lines = installed.strip().splitlines()
            if len(lines) != 1 or not lines[0].startswith('package:/data/app/'):
                raise RuntimeError('Expected one installed companion base APK')
            _, checksum = self.shell(['sha256sum', lines[0][8:]])
            if checksum.split()[0] != item['sha256']:
                raise RuntimeError('Installed companion differs from pinned APK')
            self.receipt['companions'].append({**item, **signature, 'installed_sha256': checksum.split()[0]})
        setup = ROOT / 'android/assets/loopy-termux-setup.sh'
        self.receipt['setup_sha256'] = digest(setup)
        self.receipt['setup_execution_context'] = 'run-as com.termux; runas_app, not product service'
        self.save()
        self.termux(content=setup.read_bytes(), timeout=900, log='setup-upgrade.txt')
        self.receipt['mutations'].append('latest managed helper/config upgraded; user edits preserved')
        properties = r'''python3 - <<'PY_CONFIG'
import hashlib,json,os,re
from pathlib import Path
path=Path.home()/'.termux/termux.properties'
path.parent.mkdir(mode=0o700,exist_ok=True)
if path.is_symlink():raise SystemExit('unsafe properties symlink')
before=path.read_bytes() if path.exists() else b''
text=before.decode()
line='allow-external-apps = true'
if re.search(r'^\s*allow-external-apps\s*=.*$',text,re.M):
 text=re.sub(r'^\s*allow-external-apps\s*=.*$',line,text,flags=re.M)
else:text+='\n'+line+'\n'
path.write_text(text)
os.chmod(path,0o600)
print(json.dumps({'enabled':True,'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
PY_CONFIG
termux-reload-settings
'''
        self.guard()
        self.termux(content=properties.encode(), log='external-commands-vm-only.txt')
        self.receipt['mutations'].append('allow-external-apps=true selected for this disposable VM only')
        _, versions = self.termux(command="dpkg-query -W -f='${Package} ${Version}\\n'", log='native-packages.txt')
        self.receipt['native_package_versions'] = dict(line.split(' ', 1) for line in versions.splitlines() if ' ' in line)
        _, manifest = self.termux(command='cat "$HOME/.local/share/loopy-native/installed.json"', log='installed-runtime.json')
        self.receipt['installed_runtime'] = json.loads(manifest)
        self.receipt['setup_ready'] = True
        self.receipt['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default=SERIAL)
    parser.add_argument('--sdk', type=Path, default=Path.home() / 'Library/Android/sdk')
    parser.add_argument('--vm-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('prepare', 'upgrade'), default='prepare')
    args = parser.parse_args()
    if args.serial != SERIAL: parser.error('Only explicitly owned emulator-5580 is permitted')
    preparation = VmPreparation(args.sdk, args.vm_root, args.output)
    try:
        getattr(preparation, args.mode)()
    except (OSError, ValueError, RuntimeError) as error:
        preparation.receipt['failure'] = str(error)
        preparation.save()
        raise
    print(args.output / 'receipt.json')


if __name__ == '__main__': main()
