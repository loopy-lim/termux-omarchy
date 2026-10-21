#!/usr/bin/env python3
"""Package the reviewed fresh Omarchy setup; never install or update a desktop."""
import argparse
import ast
import ctypes
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / 'third_party/termux-omarchy-setup-20261009-08.lock.json'
CATALOG_SHA = '52826eb46b8108a438e3c872b0e5e83e45ecab10be0ca82a70adf3a663287b69'
KIT = 'LoopyOmarchy-Termux-native-setup-20261009-08'
SOURCES = frozenset(('omarchy.py omarchy_android.py omarchy_android_client.py omarchy_audio.py '
    'omarchy_boot.py omarchy_commands.py omarchy_guest_install.py omarchy_host_install.py '
    'omarchy_input.py omarchy_input_install.py omarchy_install.py omarchy_machine_id.py '
    'omarchy_proot.py omarchy_proot_install.py omarchy_resources.py omarchy_runtime.py '
    'omarchy_setup.py omarchy_tools_guest.py omarchy_tools_install.py omarchy_workflow_install.py '
    'processes.py').split())
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC
README = '''Termux Omarchy fresh setup / 2026-10-09 / setup08

새 폴더에서 SHA256SUMS와 archive checksum을 확인한 뒤 실행합니다.
python ./omarchy_setup.py --bundle /absolute/path/to/owned/bundle.tar

큰 base bundle은 포함하지 않습니다. external-bundle.json의 고정 URL,
1,181,941,760 bytes와 독립 SHA256을 확인하고 소유 일반 파일로 준비합니다.
Termux Python, proot-distro 5.8.x, Termux:X11, libc++와 native graphics/audio
의존성은 별도 준비 조건입니다. 이 묶음은 Android 앱/권한을 설치하지 않습니다.

21개 Python source는 runtime11와 component 설치기로 구성됩니다.
setup08은 PRoot native 임시 경로를 전달하는 현재 runtime11을 포함합니다.
workflow는 현재 개인 bindings와 기존 나머지 14개 파일을 포함합니다.
Meta 숫자 workspace, Alt 숫자 tmux와 Alt+Space 메뉴를 유지합니다.
추가 Neovim package, VS Code, Notion·Figma 설치 경로는 포함하지 않습니다.
모든 payload와 package/signature bytes를 먼저 확인한 뒤 base → private
PRoot guard → Weston14 → guest adapters → machine-id → developer tools →
workflow → Fcitx7/config5 순서로 설치합니다. 실제 package 서명 신뢰는
설치 시 기존 guest keyring의 GPG VALIDSIG와 FULLY/ULTIMATE trust로 확인합니다.
포장 단계의 signature SHA 검증은 새 기기에서의 trusted GPG 검증이 아닙니다.

기존 설치는 현재 runtime11과 같은 bytes이며 정상 종료가 확인돼야 합니다.
legacy runtime이나 누락 파일을 이 명령으로 자동 upgrade하지 않습니다.
개인 GTK/Hyprland/셸 설정이 고정 원본과 다르면 보존하고 거절합니다.
원본 bytes/mode/identity는 private backup과 component journal에 남습니다.
부분 설치·불확실한 journal은 보존하며 자동 삭제/복구하지 않습니다.
machine-id는 빈 파일 또는 빈 etc 파일+표준 dbus symlink만 준비합니다.
프로필 삭제, 전역 proot 교체, 자동 desktop 시작/중지는 하지 않습니다.

proot-guard/는 native3만 포함합니다. PRoot COPYING, source patches와
provenance/proot-build-receipt.json을 보존합니다. provenance의 kit02 기록은
native source/build의 역사적 출처이며 새 설치 성공 증거가 아닙니다.
Weston-COPYING과 Omarchy-LICENSE, 원본 package metadata/내부 license도
보존합니다. package 출처는 provenance/tools-archives.json과
provenance/ime-preparation.json에 있습니다. 새 key import나 DB refresh는 없습니다.

이 archive의 검증은 source pin, payload member, package/signature bytes,
재현 가능한 압축과 파일 보존 경계에 한정됩니다.
fullDesktopConfigured=false, freshDeviceInstallVerified=false입니다.
원본 158개 package 요청, 51개 manual, 119개 shell QML, GPU/실제 입력 성능,
모든 앱·원격·Android/OS 통합은 계속 전체 완료 조건입니다.
현재 기기에서 개별 guard/IME/machine-id가 성공한 기록을 이 새 fresh
archive의 실기기 설치 성공으로 재사용하지 않습니다.

각 파일은 manifest.json, 고정 출처는 source-catalog.json으로 대조합니다.
manifest는 자기 자신과 SHA256SUMS를 제외한 모든 파일을 기록합니다.
SHA256SUMS는 자기 자신을 제외한 모든 파일을 기록하며 archive SHA는 전체를 덮습니다.
부분 packaging 실패의 private stage는 보존합니다. 완료 receipt 없이 배포하지 않습니다.
'''


def require(value, reason='setup-package-boundary'):
    if not value: raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(row):
    return (json.dumps(row, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()


def relative(name):
    require(isinstance(name, str) and 0 < len(name) <= 512)
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and all(p not in ('', '.', '..') for p in path.parts))
    return path


def fingerprint(row):
    return (row.st_dev, row.st_ino, row.st_uid, row.st_mode, row.st_size,
            row.st_mtime_ns, row.st_ctime_ns, row.st_nlink)


def directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    row = os.fstat(fd)
    if row.st_uid != os.getuid() or row.st_mode & 0o022:
        os.close(fd); raise ValueError('setup-package-directory')
    return fd


def read_owned(root, name, maximum):
    path = relative(name); fd = directory(root)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
            row = os.fstat(fd)
            require(row.st_uid == os.getuid() and not row.st_mode & 0o022)
        source = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=fd)
        with os.fdopen(source, 'rb') as stream:
            before = fingerprint(os.fstat(stream.fileno()))
            require(stat.S_ISREG(before[3]) and before[2] == os.getuid() and before[-1] == 1
                    and not before[3] & 0o022 and before[4] <= maximum)
            data = stream.read(maximum + 1)
            require(len(data) <= maximum and fingerprint(os.fstat(stream.fileno())) == before
                    and fingerprint(os.stat(path.name, dir_fd=fd, follow_symlinks=False)) == before,
                    'setup-package-input-changed')
            return data
    finally: os.close(fd)


def assignment(data, key):
    for node in ast.parse(data).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == key for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('setup-package-source-contract')


def component(data):
    node = next(n for n in ast.parse(data).body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'COMPONENT' for t in n.targets))
    require(isinstance(node.value, ast.Call))
    return [ast.literal_eval(n) for n in node.value.args[:6]]


def tar_payload(data, payload, manifest, prefix, count):
    files = json.loads(data[manifest])['files']; require(len(files) == count)
    expected = {prefix + '/' + name: row for name, row in files.items()}
    for name in expected: relative(name)
    parents = {str(p) for name in expected for p in PurePosixPath(name).parents if str(p) != '.'}
    seen = set(); found = set()
    with tarfile.open(fileobj=io.BytesIO(data[payload]), mode='r:') as archive:
        for row in archive:
            relative(row.name); require(row.name not in seen); seen.add(row.name)
            if row.isdir():
                require(prefix == 'weston-host' and row.name in parents and row.mode in (0o700, 0o755))
            else:
                require(row.isfile() and row.name in expected)
                mode = expected[row.name]['mode'] if prefix == 'weston-host' else 0o600
                require(row.mode == mode and 0 <= row.size <= len(data[payload]))
                require(sha(archive.extractfile(row).read()) == expected[row.name]['sha256'])
                found.add(row.name)
    require(found == set(expected))
    if prefix == 'weston-host': require(seen == found | parents)


def validate(repo):
    raw = read_owned(CATALOG.parent, CATALOG.name, 131072)
    require(sha(raw) == CATALOG_SHA, 'setup-package-catalog-sha')
    catalog = json.loads(raw)
    require(catalog['schema'] == 1 and catalog['kit'] == KIT and set(catalog['sourceClosure']) == SOURCES)
    data, modes = {}, {}
    for name, row in catalog['files'].items():
        relative(name); require(set(row) == {'source', 'sha256', 'bytes', 'mode'} and row['mode'] in (0o600, 0o700))
        content = read_owned(repo, row['source'], row['bytes'])
        require(len(content) == row['bytes'] and sha(content) == row['sha256'], 'setup-package-input-sha')
        data[name], modes[name] = content, row['mode']
    require({n for n in data if n.endswith('.py')} == SOURCES)
    pending, reached = ['omarchy_setup.py'], set()
    while pending:
        name = pending.pop()
        if name in reached: continue
        require(name in SOURCES, 'setup-package-import-closure'); reached.add(name)
        for node in ast.walk(ast.parse(data[name])):
            imports = [n.name for n in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            pending.extend(n + '.py' for n in imports if n.startswith('omarchy') or n == 'processes')
    runtime = assignment(data['omarchy_install.py'], 'RUNTIME_SHA')
    require(len(runtime) == 11 and reached | set(runtime) == SOURCES)
    require(all(name in data and sha(data[name]) == pin for name, pin in runtime.items()))
    require(catalog['externalBundle']['sha256'] == assignment(data['omarchy_install.py'], 'OUTER_SHA')
            and catalog['externalBundle']['bytes'] == assignment(data['omarchy_install.py'], 'OUTER_BYTES'))
    for module, payload, manifest, count, prefix in (
        ('omarchy_host_install.py','payload.tar','payload-manifest.json',87,'weston-host'),
        ('omarchy_guest_install.py','guest-payload.tar','guest-manifest.json',11,'guest'),
        ('omarchy_workflow_install.py','workflow-payload.tar','workflow-manifest.json',15,'guest'),
        ('omarchy_input_install.py','input-config-payload.tar','input-config-manifest.json',5,'guest')):
        pins = component(data[module])[:4] if module in ('omarchy_workflow_install.py','omarchy_input_install.py') else [
            assignment(data[module], key) for key in ('PAYLOAD_SHA','PAYLOAD_BYTES','MANIFEST_SHA','MANIFEST_BYTES')]
        require([sha(data[payload]),len(data[payload]),sha(data[manifest]),len(data[manifest])] == pins)
        tar_payload(data,payload,manifest,prefix,count)
    require(sha(data['omarchy_tools_guest.py']) == assignment(data['omarchy_tools_install.py'],'GUEST_SHA'))
    for prefix, manifest, key, count in (('', 'tools-manifest.json','MANIFEST_SHA',29),
                                        ('korean-input/','ime-manifest.json','IME_MANIFEST_SHA',7)):
        require(sha(data[prefix+manifest]) == assignment(data['omarchy_tools_guest.py'],key))
        rows = json.loads(data[prefix+manifest])['packages']; require(len(rows) == count)
        for row in rows:
            for suffix, byte_key, sha_key in (('', 'bytes','sha256'),('.sig','signatureBytes','signatureSHA256')):
                content=data[prefix+row['file']+suffix]
                require(len(content)==row[byte_key] and sha(content)==row[sha_key])
    for name,pin in assignment(data['omarchy_proot.py'],'FILES').items():
        require(sha(data['proot-guard/'+name])==pin)
    require({n for n in data if n.startswith('proot-guard/')} ==
            {'proot-guard/proot','proot-guard/loader','proot-guard/libandroid-shmem.so'})
    provenance=json.loads(data['provenance/proot-guard-update-kit02.json'])
    require(provenance['buildReceiptSHA256']==sha(data['provenance/proot-build-receipt.json']))
    require(all(sha(data[n])==pin for n,pin in provenance['sourcePatchSHA256'].items()))
    data.update({'source-catalog.json':raw,'external-bundle.json':encoded(catalog['externalBundle']),
                 'README.txt':README.encode()})
    modes.update({name:0o600 for name in data if name not in modes})
    return catalog,data,modes


def publish(fd, source, target):
    libc=ctypes.CDLL(None,use_errno=True)
    rename,flags=(libc.renameat2,1) if hasattr(libc,'renameat2') else (libc.renameatx_np,4)
    rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    rename.restype=ctypes.c_int
    if rename(fd,os.fsencode(source),fd,os.fsencode(target),flags):
        number=ctypes.get_errno(); raise OSError(number,os.strerror(number),target)
    os.fsync(fd)


def write_file(path,data,mode=0o600):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|NOFOLLOW,0o600),'wb') as stream:
        stream.write(data); stream.flush(); os.fchmod(stream.fileno(),mode); os.fsync(stream.fileno())


def package(repo,output):
    repo=Path(repo).resolve(strict=True); output=Path(output).absolute()
    require(output.parent.resolve(strict=True)==output.parent,'setup-package-output-symlink')
    fd=directory(output.parent)
    names=[output.name,output.name+'.tar.gz',output.name+'.tar.gz.sha256',output.name+'.packaging.json']
    try:
        require(all(not os.path.lexists(output.parent/n) for n in names),'setup-package-output-exists')
        catalog,data,modes=validate(repo)  # All source, payload and signature pins before any output write.
        manifest=dict(schema=1,kit=KIT,componentCounts=catalog['componentCounts'],sourceCatalogSHA256=CATALOG_SHA,
            fullDesktopConfigured=False,freshDeviceInstallVerified=False,trustedSignaturesVerifiedByPackager=False,
            files={n:dict(sha256=sha(b),bytes=len(b),mode=modes[n]) for n,b in sorted(data.items())})
        data['manifest.json']=encoded(manifest); modes['manifest.json']=0o600
        data['SHA256SUMS']=''.join(sha(data[n])+'  '+n+'\n' for n in sorted(data)).encode(); modes['SHA256SUMS']=0o600
        stage=Path(tempfile.mkdtemp(prefix='.fresh-setup-stage-',dir=output.parent))
        kit=stage/'kit'; kit.mkdir(mode=0o700)
        for name,content in sorted(data.items()):
            target=kit/name; target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            write_file(target,content,modes[name])
        dirs={str(p) for name in data for p in PurePosixPath(name).parents if str(p)!='.'}
        for name in sorted(dirs|{'.'},reverse=True):
            child=directory(kit/name)
            try: os.fsync(child)
            finally: os.close(child)
        archive=stage/'archive'
        with os.fdopen(os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL|NOFOLLOW,0o600),'wb') as target:
            with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as zipped:
                with tarfile.open(fileobj=zipped,mode='w',format=tarfile.USTAR_FORMAT) as tar:
                    for name in sorted({KIT}|{KIT+'/'+n for n in dirs}):
                        row=tarfile.TarInfo(name); row.type=tarfile.DIRTYPE; row.mode=0o700; tar.addfile(row)
                    for name,content in sorted(data.items()):
                        row=tarfile.TarInfo(KIT+'/'+name); row.mode=modes[name]; row.size=len(content)
                        tar.addfile(row,io.BytesIO(content))
            target.flush(); os.fsync(target.fileno())
        for name,content in data.items(): require(read_owned(kit,name,len(content))==content,'setup-package-output-changed')
        archive_data=read_owned(stage,'archive',128*1024*1024); archive_sha=sha(archive_data)
        with tarfile.open(fileobj=io.BytesIO(archive_data),mode='r:gz') as tar:
            rows=[r for r in tar if r.isfile()]
            require(len(rows)==len(data) and {r.name for r in rows}=={KIT+'/'+n for n in data})
            require(all(tar.extractfile(r).read()==data[r.name[len(KIT)+1:]] for r in rows))
        result=dict(schema=1,status='packaged-verified-bytes',kit=KIT,archiveSHA256=archive_sha,
            archiveBytes=len(archive_data),archiveFileCount=len(data),componentCounts=catalog['componentCounts'],
            manifestSHA256=sha(data['manifest.json']),sourceCatalogSHA256=CATALOG_SHA,
            fullDesktopConfigured=False,freshDeviceInstallVerified=False,trustedSignaturesVerifiedByPackager=False)
        write_file(stage/'checksum',(archive_sha+'  '+names[1]+'\n').encode())
        write_file(stage/'receipt',encoded(result))
        for source,target in zip(('kit','archive','checksum','receipt'),names):
            publish(fd,stage.name+'/'+source,target)
        stage.rmdir(); os.fsync(fd)
        return result
    finally: os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=REPO)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(package(args.repo,args.output),sort_keys=True)); return 0
    except (ValueError,OSError,KeyError,TypeError,SyntaxError,tarfile.TarError):
        print('{"schema":1,"status":"failed","reason":"setup-package-boundary"}'); return 1


if __name__=='__main__': raise SystemExit(main())
