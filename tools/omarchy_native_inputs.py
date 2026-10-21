"""Bind the APK's Hyprland component to its full prepared source and actual ARM build."""
import hashlib
import json
from pathlib import Path
try:
    from tools.hyprtoolkit_inputs import check as check_toolkit
    from tools.omarchy_refresh_inputs import _validate as check_refresh
except ModuleNotFoundError:
    from hyprtoolkit_inputs import check as check_toolkit
    from omarchy_refresh_inputs import _validate as check_refresh

SHA = '7d65f7ea3c4c53f624b2dc43928c3b7271f1c90ee1d65ae232ce99190e00a600'
PRIOR = '1c61c2910a7fe92cd716c58cb57b3cc7d67c1b181040138ea30d2f041038ddfc'
BASE = '4491b2dbc8c6e15596ec05c4fbcefbaa2d97814e616dc619dd24be8be9662b92'
IMAGE = '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86'
SIZE = 17319776


def checked_inputs(root):
    root = Path(root).absolute()
    if not (root / 'android/assets/omarchy-runtime.properties').exists() \
            and not (root / 'android/assets/omarchy-native').exists():
        return []
    inputs = [root / 'tools/omarchy_native_inputs.py']

    def regular(name, expected=None, maximum=64 * 1024**2):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Native component input must remain in the project')
        path = root / relative
        if (not path.is_file() or path.is_symlink() or path.resolve() != root.resolve() / relative
                or not 0 <= path.stat().st_size <= maximum):
            raise ValueError('Bounded regular native component input required: ' + name)
        data = path.read_bytes()
        if expected is not None and hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Native component input identity differs: ' + name)
        inputs.append(path)
        return data

    record = json.loads(regular('android/assets/omarchy-native/provenance.json', maximum=65536))
    if record.get('schema') == 2:
        candidate = record.get('component_candidate')
        if candidate != 'build/omarchy-refresh-20261008' or record.get('base_image_sha256') != IMAGE \
                or record.get('prior_binary_sha256') != SHA:
            raise ValueError('Pinned refresh component pair and previous compositor required')
        component_receipt = candidate + '/component-receipt.json'
        regular(component_receipt, record.get('component_receipt_sha256'), 1048576)
        refreshed, bindings = check_refresh(root, candidate)
        inputs.extend(refreshed)
        expected = {'Aquamarine': ('47e20a15c246b73880ec637c5334316ba5b85ade668537aade4d8484aec548a4', 1741376),
                    'Hyprland': ('f9bef874e04f4cc16b0e18d579671d002c868927886c4b528eeed1e0307a8955', 17319752)}
        for item in bindings:
            sha, size = expected[item['component']]
            if (item['sha256'], item['bytes']) != (sha, size):
                raise ValueError('Reviewed refresh binary identity differs')
            name = 'android/assets/omarchy-native/' + ('Hyprland' if item['component'] == 'Hyprland' else 'aquamarine/libaquamarine.so.0.15.1')
            if len(regular(name, sha, size)) != size:
                raise ValueError('Shipped refresh component size differs')
        if record.get('binary_sha256') != expected['Hyprland'][0] or record.get('binary_bytes') != expected['Hyprland'][1] \
                or record.get('base_binary_sha256') != BASE:
            raise ValueError('Shipped compositor and stock image preimage differ')
        reused_name = candidate + '/reused/build-inputs.json'
        reused = json.loads(regular(reused_name, record.get('reused_inputs_sha256'), 1048576))
        build = json.loads(regular(candidate + '/hyprland-build-receipt.json'))
        if reused.get('schema') != 1 or reused.get('status') != 'baseline-objects-byte-reproduced' \
                or reused.get('baseline_relink_sha256') != SHA or build.get('baseline_relink_sha256') != SHA:
            raise ValueError('Reused baseline objects were not byte-reproduced')
        baseline = json.loads(regular(reused['baseline_build_receipt'], reused['baseline_build_receipt_sha256']))
        if baseline['binaries']['Hyprland']['sha256'] != SHA or build['baseline_build_receipt_sha256'] != reused['baseline_build_receipt_sha256']:
            raise ValueError('Reused object source baseline differs')
        inventory = reused.get('files', {})
        required = {'libhyprland_lib.a', 'main.cpp.o', 'liblibudis86.a', 'compile_commands.json', 'baseline-relink.json'}
        if set(Path(name).name for name in inventory) != required or len(inventory) != len(required):
            raise ValueError('Complete reused object and command inventory required')
        for name, identity in inventory.items():
            if str(Path(name).parent) != candidate + '/reused':
                raise ValueError('Reused objects must remain inside the frozen candidate')
            maximum = 128 * 1024**2 if Path(name).name == 'libhyprland_lib.a' else 8 * 1024**2
            if len(regular(name, identity['sha256'], maximum)) != identity['bytes']:
                raise ValueError('Reused input byte size differs')
        if inventory[candidate + '/reused/libhyprland_lib.a']['sha256'] != build['reused_archive_sha256'] \
                or inventory[candidate + '/reused/compile_commands.json']['sha256'] != build['captured_compile_commands_sha256']:
            raise ValueError('Frozen reused objects and captured compiler command differ')
        proof = json.loads((root / (candidate + '/reused/baseline-relink.json')).read_text())
        if proof.get('binary_sha256') != SHA or proof.get('input_archive_sha256') != build['reused_archive_sha256'] \
                or proof.get('command') != reused.get('link_command') or proof.get('command') != build['build_commands'][-1]:
            raise ValueError('Baseline relink and candidate linker commands differ')
        aq_record = json.loads(regular('android/assets/omarchy-native/aquamarine/provenance.json', maximum=65536))
        if aq_record.get('schema') != 1 or aq_record.get('component_candidate') != candidate \
                or aq_record.get('guest') != '/usr/lib/libaquamarine.so.0.15.1' \
                or aq_record.get('base_binary_sha256') != '4b662e8a42595592378e970a5bdae1156f93ab909449d01c566be2d2c5bb4461' \
                or aq_record.get('base_binary_bytes') != 1736888 or aq_record.get('base_image_sha256') != IMAGE \
                or aq_record.get('component_receipt_sha256') != record['component_receipt_sha256'] \
                or (aq_record.get('binary_sha256'), aq_record.get('binary_bytes')) != expected['Aquamarine']:
            raise ValueError('Aquamarine asset provenance is not paired with the compositor')
        for name, identity in record['licenses'].items():
            regular('android/assets/omarchy-native/licenses/' + name, identity, 1048576)
        check_toolkit(root, regular)
        return sorted(set(inputs))
    if (record.get('schema') != 1 or record.get('binary_sha256') != SHA
            or record.get('binary_bytes') != SIZE or record.get('base_binary_sha256') != BASE
            or record.get('base_image_sha256') != IMAGE or record.get('prior_binary_sha256') != PRIOR):
        raise ValueError('Pinned native component and base image identity required')
    binary = regular('android/assets/omarchy-native/Hyprland', SHA, SIZE)
    if len(binary) != SIZE: raise ValueError('Native component size differs')
    catalog = regular('android/assets/omarchy-runtime.properties').decode()
    if dict(line.split('=', 1) for line in catalog.splitlines())['archive_sha256'] != IMAGE:
        raise ValueError('Native component is incompatible with the catalog image')
    dependencies = record['inputs']
    if not isinstance(dependencies, dict) or not dependencies:
        raise ValueError('Native component provenance inputs required')
    for name, expected in dependencies.items(): regular(name, expected)
    for key in ('build_receipt', 'source_receipt', 'producer', 'baseline_receipt'):
        if record[key] not in dependencies: raise ValueError('Unpinned native build dependency: ' + key)
    build = json.loads((root / record['build_receipt']).read_text())
    source = json.loads((root / record['source_receipt']).read_text())
    baseline = json.loads((root / record['baseline_receipt']).read_text())
    lock = json.loads(regular('third_party/omarchy.lock.json', build['lock_sha256']))
    if (build.get('build_exit') != 0 or build.get('architecture') != 'aarch64'
            or build.get('prior_binary_sha256') != PRIOR
            or baseline['binaries']['Hyprland']['sha256'] != PRIOR
            or build['binaries']['Hyprland']['sha256'] != SHA
            or build['binaries']['Hyprland']['bytes'] != SIZE
            or build['producer_sha256'] != dependencies[record['producer']]
            or build['baseline_receipt_sha256'] != dependencies[record['baseline_receipt']]
            or build['source_files'] != source['source_files'] or build['patches'] != lock['hyprland_patches']
            or source['lock_sha256'] != build['lock_sha256']):
        raise ValueError('Native build does not match the shipped component/source')
    for patch in lock['hyprland_patches']:
        regular(patch['patch'], patch['patch_sha256'])
        regular(patch['metadata_file'], patch['metadata_sha256'])
    for name, expected in source['source_files'].items():
        regular(str(Path(record['source_directory']) / name), expected)
    for name, expected in record['licenses'].items():
        regular('android/assets/omarchy-native/licenses/' + name, expected, 1048576)
    check_toolkit(root, regular)
    return sorted(set(inputs))
