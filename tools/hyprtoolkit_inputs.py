"""Bind the original toolkit library to its immutable source and real ARM build."""
import json
from pathlib import Path

SHA = '2599af0dac9d026d327aacbc594c5ae692cab324ff7092e86480b8772aa43eb9'
BASE = 'fc9424a4436c1bb3f9639ddd77887c7c83c71d4c30786d757102f5816703856a'
IMAGE = '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86'
SIZE = 2517928


def check(root, regular):
    """Use the owning publisher's bounded, no-link file collector."""
    regular('tools/hyprtoolkit_inputs.py')
    prefix = 'android/assets/omarchy-native/hyprtoolkit/'
    record = json.loads(regular(prefix + 'provenance.json', maximum=65536))
    if (record.get('schema') != 1 or record.get('binary_sha256') != SHA
            or record.get('binary_bytes') != SIZE or record.get('base_binary_sha256') != BASE
            or record.get('base_binary_bytes') != 2102288 or record.get('base_image_sha256') != IMAGE):
        raise ValueError('Pinned toolkit and base image identity required')
    if len(regular(prefix + 'libhyprtoolkit.so.0.6.0', SHA, SIZE)) != SIZE:
        raise ValueError('Toolkit component size differs')
    inputs = record['inputs']
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError('Toolkit build provenance inputs required')
    for name, expected in inputs.items(): regular(name, expected)
    for key in ('build_receipt', 'source_receipt', 'producer', 'export_producer'):
        if record[key] not in inputs: raise ValueError('Unpinned toolkit dependency: ' + key)
    build = json.loads((root / record['build_receipt']).read_text())
    source = json.loads((root / record['source_receipt']).read_text())
    lock = json.loads(regular('third_party/hyprtoolkit.lock.json', build['lock_sha256']))
    if (build.get('status') != 'compiled-in-reference-vm' or build.get('build_exit') != 0
            or build.get('architecture') != 'aarch64' or build.get('binary_sha256') != SHA
            or build.get('binary_bytes') != SIZE or build['producer_sha256'] != inputs[record['producer']]
            or build['source_files'] != source['source_files'] or build['patches'] != lock['patches']
            or source['lock_sha256'] != build['lock_sha256'] or build['upstream'] != lock['upstream']):
        raise ValueError('Toolkit build differs from shipped source or component')
    for patch in lock['patches']:
        regular(patch['patch'], patch['patch_sha256'])
        regular(patch['metadata_file'], patch['metadata_sha256'])
    for name, expected in source['source_files'].items():
        regular(str(Path(record['source_directory']) / name), expected)
    regular(prefix + 'LICENSE', record['license_sha256'], 1048576)
