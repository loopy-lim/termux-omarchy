"""Bind the separate watchdog asset to the frozen real ARM build and input closure."""
import hashlib
import json
import posixpath
from pathlib import Path, PurePosixPath
try:
    from tools.watchdog_elf import inspect
except ModuleNotFoundError:
    from watchdog_elf import inspect

CANDIDATE = 'build/omarchy-watchdog-20261008-04'
SHA = 'cbbba746c29b30736b04d23501687eadf0e6d36ed4cd9d5c942ad13481b2be7c'
BYTES = 301856
BASE = '29f40097d5fe3ded68c57a9b53d6a39e1051cafb9d05474a205316dfe1baf8d0'
BASE_BYTES = 264536
IMAGE = '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86'
BUILD_SHA = 'a72c253956652d92111a96cb173505ef4f383b195131efb84bf543d2b71dff71'
PROCESS_SHA = 'd0e2d270828c743765855c66dd4a1a39af87181e2324439d894966e5c1c0eb61'
CONFIG_SHA = '9692a6fe4ad3169f7baf1d7135d20248de488165297c4a6b5756182eaed033fd'
DEPLOYMENT = ('tools/publish_omarchy_watchdog_v4.py', 'tools/omarchy_watchdog_v4_inputs.py', 'tools/watchdog_elf.py')


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
    config = json.loads(regular(CANDIDATE + '/process-config-regression.json', CONFIG_SHA, maximum=65536).read_text())
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
    expected = set(snapshot) | {CANDIDATE + '/build-receipt.json', CANDIDATE + '/process-regression.json', CANDIDATE + '/process-config-regression.json'}
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
    for proof, producer in ((process, 'tools/probe_omarchy_watchdog_component_v4.py'),
                            (config, 'tools/probe_omarchy_watchdog_component_v4_config.py')):
        if proof.get('status') != 'passed' or proof.get('passed') != 8 or len(proof.get('cases', [])) != 8 \
                or not all(case.get('passed') is True for case in proof['cases']) \
                or proof.get('binary_sha256') != SHA or proof.get('build_receipt_sha256') != BUILD_SHA \
                or proof.get('physical_device') is not False or proof.get('hardware_gpu') is not False:
            raise ValueError('Matched actual ARM watchdog/config process proof required')
        regular(producer, proof['producer_sha256'])
    regular('tools/watchdog_elf.py')
    regular('tools/omarchy_watchdog_v4_inputs.py')
    return sorted(set(inputs))


def provenance(root):
    root = Path(root)
    return {'schema': 1, 'guest': '/usr/bin/start-hyprland', 'component_candidate': CANDIDATE,
            'binary_sha256': SHA, 'binary_bytes': BYTES, 'base_binary_sha256': BASE,
            'base_binary_bytes': BASE_BYTES, 'base_image_sha256': IMAGE,
            'build_receipt_sha256': BUILD_SHA, 'process_receipt_sha256': PROCESS_SHA, 'config_receipt_sha256': CONFIG_SHA,
            'baseline_matches_stock': False, 'physical_device': False, 'hardware_gpu': False,
            'inputs': {name: digest(root / name) for name in DEPLOYMENT},
            'licenses': {'LICENSE': digest(root / CANDIDATE / 'candidate-source/LICENSE'),
                         'Glaze-LICENSE': digest(root / CANDIDATE / 'glaze-source/LICENSE')}}


def checked_inputs(root):
    root, inputs, regular = collector(root)
    assets = root / 'android/assets/omarchy-watchdog-v4'
    if not assets.exists() and not assets.is_symlink():
        if (root / 'android/assets/omarchy-runtime.properties').exists():
            raise ValueError('Omarchy watchdog assets are missing')
        return []
    inputs.extend(candidate_inputs(root))
    record = json.loads(regular('android/assets/omarchy-watchdog-v4/provenance.json', maximum=65536).read_text())
    if record != provenance(root): raise ValueError('Shipped watchdog provenance differs')
    regular('android/assets/omarchy-watchdog-v4/start-hyprland', SHA, BYTES)
    for name, sha in record['licenses'].items(): regular('android/assets/omarchy-watchdog-v4/' + name, sha)
    for name, sha in record['inputs'].items(): regular(name, sha)
    if {p.name for p in assets.iterdir()} != {'start-hyprland', 'LICENSE', 'Glaze-LICENSE', 'provenance.json'}:
        raise ValueError('Extra watchdog asset input')
    return sorted(set(inputs))
