"""Pin the existing editing policy and bounded Wayland input client reused by Arch."""
import hashlib
import json
from pathlib import Path

NAMES = ('mac_commands.py', 'loopy_chords.py', 'loopy_input.py', 'loopy_ime.py', 'loopy_input_trace.py')


def checked_inputs(root):
    root = Path(root)
    assets = root / 'android/assets/omarchy-bridge'
    provenance = assets / 'input-sources.json'
    if not provenance.exists() and not provenance.is_symlink():
        if (root / 'android/assets/omarchy-runtime.properties').exists():
            raise ValueError('Original Omarchy requires the pinned native input client')
        return []
    def regular(path, maximum):
        if (path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum
                or path.resolve() != root.resolve() / path.relative_to(root)):
            raise ValueError('Bounded regular native input source required')
        return path.read_bytes()
    record = json.loads(regular(provenance, 65536))
    if (not isinstance(record, dict) or set(record) != {'schema', 'files'}
            or type(record['schema']) is not int or record['schema'] != 1
            or not isinstance(record['files'], dict) or set(record['files']) != set(NAMES)):
        raise ValueError('Exact native input source inventory required')
    inputs = [Path(__file__).resolve(), provenance]
    for name in NAMES:
        asset = assets / name
        source = root / 'guest/desktop/usr/local/lib/loopy' / name
        data = regular(asset, 262144)
        if regular(source, 262144) != data or hashlib.sha256(data).hexdigest() != record['files'][name]:
            raise ValueError('Native input source changed; regenerate the matched public asset: ' + name)
        inputs.extend((asset, source))
    return inputs
