"""Bind the separate watchdog asset to the frozen real ARM build and input closure."""
import hashlib
import json
import posixpath
from pathlib import Path, PurePosixPath
try:
    from tools.watchdog_elf import inspect
except ModuleNotFoundError:
    from watchdog_elf import inspect

CANDIDATE = 'build/omarchy-watchdog-20261008-03'
SHA = '39f0a45a6cf881b10e16244cee9e508d80bb9db8a7ce6b19b83f99bcd6adbca4'
BYTES = 301856
BASE = '29f40097d5fe3ded68c57a9b53d6a39e1051cafb9d05474a205316dfe1baf8d0'
BASE_BYTES = 264536
IMAGE = '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86'
BUILD_SHA = '0d0c78f4502a25fb2e9bbb70420a4b970b3b24051093bd7c4669e29a3effa96d'
PROCESS_SHA = '7633517a9c91fd7fcb75ab48437ea90eec99203b2a95ec7dcb37d905dcd13f7d'
DEPLOYMENT = ('tools/publish_omarchy_watchdog.py', 'tools/omarchy_watchdog_inputs.py', 'tools/watchdog_elf.py')


def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def collector(root):
    root, inputs = Path(root).absolute(), []

    def regular(name, sha=None, size=None, maximum=128 * 1024**2):
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('Watchdog input must remain project relative')
        path = root / str(relative)
        if path.is_symlink() or not path.is_file() or path.resolve() != root.resolve() / str(relative) \
                or not 0 <= path.stat().st_size <= maximum:
            raise ValueError('Bounded unredirected regular watchdog input required: ' + name)
        if (sha is not None and digest(path) != sha) or (size is not None and path.stat().st_size != size):
            raise ValueError('Watchdog input identity differs: ' + name)
        inputs.append(path)
        return path
    return root, inputs, regular


def candidate_inputs(root):
    root, inputs, regular = collector(root)
    build = json.loads(regular(CANDIDATE + '/build-receipt.json', BUILD_SHA, maximum=1024**2).read_text())
    process = json.loads(regular(CANDIDATE + '/process-regression.json', PROCESS_SHA, maximum=65536).read_text())
    if build.get('schema_version') != 1 or build.get('status') != 'compiled-in-reference-vm' \
            or build.get('component') != 'start-hyprland' or build.get('architecture') != 'aarch64' \
            or build.get('baseline_matches_stock') is not False \
            or any(build.get(k) is not False for k in ('packaged', 'physical_device', 'hardware_gpu')):
        raise ValueError('Frozen ARM watchdog build evidence required')
    snapshot = build.get('standalone_snapshot', {})
    if not isinstance(snapshot, dict) or len(snapshot) != 1265:
        raise ValueError('Complete frozen watchdog snapshot required')
    for name, identity in snapshot.items():
        if not name.startswith(CANDIDATE + '/') or set(identity) != {'sha256', 'bytes'} \
                or type(identity['bytes']) is not int:
            raise ValueError('Watchdog snapshot input outside frozen candidate')
        regular(name, identity['sha256'], identity['bytes'])
    expected = set(snapshot) | {CANDIDATE + '/build-receipt.json', CANDIDATE + '/process-regression.json'}
    actual = set()
    for path in (root / CANDIDATE).rglob('*'):
        if path.is_symlink(): raise ValueError('Redirected watchdog snapshot entry')
        if path.is_file(): actual.add(str(path.relative_to(root)))
    if actual != expected: raise ValueError('Extra or missing frozen watchdog input')
    mapping = build['frozen_path_mapping']
    for group in ('source_guard_inputs', 'compiler_inputs', 'runtime_inputs', 'sysroot_inputs', 'compiled_local_inputs'):
        for original, identity in build[group].items():
            mapped = mapping.get(original)
            name = posixpath.normpath(mapped) if isinstance(mapped, str) else None
            if name not in snapshot or snapshot[name] != {'sha256': identity['sha256'], 'bytes': identity['bytes']}:
                raise ValueError('Missing original watchdog build input mapping')
            if group == 'source_guard_inputs' and original.startswith('/workspace/'):
                regular(original[len('/workspace/'):], identity['sha256'], identity['bytes'])
    source_path = CANDIDATE + '/candidate-source/loopy-watchdog-source-receipt.json'
    source = json.loads(regular(source_path, build['source_receipt_sha256'], maximum=65536).read_text())
    if source != build['source_receipt'] or source.get('status') != 'source-prepared' \
            or any(source.get(k) is not False for k in ('compiled', 'packaged', 'android_gui_accepted')):
        raise ValueError('Watchdog source receipt semantics differ')
    for name, sha in source['source_files'].items(): regular(CANDIDATE + '/candidate-source/' + name, sha)
    binary = regular(CANDIDATE + '/components/start-hyprland', SHA, BYTES)
    identity = build['binaries']['candidate']
    if identity != dict(inspect(binary.read_bytes()), sha256=SHA, bytes=BYTES) \
            or build['fresh_repeat_sha256']['candidate'] != SHA \
            or build['fresh_repeat_sha256']['baseline'] != build['binaries']['baseline']['sha256']:
        raise ValueError('Independent watchdog ELF or repeated build differs')
    stock = build['stock_rootfs_preimage']
    if stock['sha256'] != BASE or stock['bytes'] != BASE_BYTES:
        raise ValueError('Original watchdog rootfs preimage differs')
    if process.get('status') != 'passed' or process.get('passed') != 8 or len(process.get('cases', [])) != 8 \
            or not all(case.get('passed') is True for case in process['cases']) \
            or process.get('binary_sha256') != SHA or process.get('build_receipt_sha256') != BUILD_SHA \
            or process.get('physical_device') is not False or process.get('hardware_gpu') is not False:
        raise ValueError('Matched actual ARM watchdog process proof required')
    regular('tools/probe_omarchy_watchdog_component.py', process['producer_sha256'])
    regular('tools/watchdog_elf.py')
    regular('tools/omarchy_watchdog_inputs.py')
    return sorted(set(inputs))


def provenance(root):
    root = Path(root)
    return {'schema': 1, 'guest': '/usr/bin/start-hyprland', 'component_candidate': CANDIDATE,
            'binary_sha256': SHA, 'binary_bytes': BYTES, 'base_binary_sha256': BASE,
            'base_binary_bytes': BASE_BYTES, 'base_image_sha256': IMAGE,
            'build_receipt_sha256': BUILD_SHA, 'process_receipt_sha256': PROCESS_SHA,
            'baseline_matches_stock': False, 'physical_device': False, 'hardware_gpu': False,
            'inputs': {name: digest(root / name) for name in DEPLOYMENT},
            'licenses': {'LICENSE': digest(root / CANDIDATE / 'candidate-source/LICENSE'),
                         'Glaze-LICENSE': digest(root / CANDIDATE / 'glaze-source/LICENSE')}}


def checked_inputs(root):
    root, inputs, regular = collector(root)
    assets = root / 'android/assets/omarchy-watchdog'
    if not assets.exists() and not assets.is_symlink():
        if (root / 'android/assets/omarchy-runtime.properties').exists():
            raise ValueError('Omarchy watchdog assets are missing')
        return []
    inputs.extend(candidate_inputs(root))
    record = json.loads(regular('android/assets/omarchy-watchdog/provenance.json', maximum=65536).read_text())
    if record != provenance(root): raise ValueError('Shipped watchdog provenance differs')
    regular('android/assets/omarchy-watchdog/start-hyprland', SHA, BYTES)
    for name, sha in record['licenses'].items(): regular('android/assets/omarchy-watchdog/' + name, sha)
    for name, sha in record['inputs'].items(): regular(name, sha)
    if {p.name for p in assets.iterdir()} != {'start-hyprland', 'LICENSE', 'Glaze-LICENSE', 'provenance.json'}:
        raise ValueError('Extra watchdog asset input')
    return sorted(set(inputs))
