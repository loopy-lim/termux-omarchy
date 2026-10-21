#!/usr/bin/env python3
"""Prepare the original pinned toolkit plus guarded rootless graphics changes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_omarchy_graphics import apply_guarded_patch, extract_source
from tools.prepare_omarchy import relative, verify_file


def prepare(destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Existing toolkit source is preserved')
    lock_path = ROOT / 'third_party/hyprtoolkit.lock.json'
    lock = json.loads(lock_path.read_text())
    identity = lock['upstream']
    if lock['schema'] != 1 or identity['repo'] != 'hyprwm/hyprtoolkit' or identity['version'] != '0.6.0':
        raise ValueError('Pinned original toolkit required')
    archive = ROOT / relative(identity['archive_file'])
    verify_file(archive, identity['archive_sha256'], identity['archive_bytes'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ht-', dir=destination.parent) as folder:
        candidate = Path(folder) / 'source'
        extract_source(archive, candidate, identity['commit'], project='hyprtoolkit')
        actual = {str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in candidate.rglob('*') if p.is_file()}
        if actual != lock['source_files']:
            raise ValueError('Toolkit upstream file identity differs')
        for entry in lock['patches']:
            metadata = ROOT / relative(entry['metadata_file'])
            verify_file(metadata, entry['metadata_sha256'])
            details = json.loads(metadata.read_text())
            if details['upstream_commit'] != identity['commit']:
                raise ValueError('Toolkit patch upstream differs')
            apply_guarded_patch(candidate, ROOT / relative(entry['patch']), details, project='hyprtoolkit')
        record = {'status': 'source-prepared', 'upstream': identity, 'architecture': 'aarch64',
            'lock_sha256': hashlib.sha256(lock_path.read_bytes()).hexdigest(), 'patches': lock['patches'],
            'source_files': {str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(candidate.rglob('*')) if p.is_file()}}
        (candidate / 'loopy-source-receipt.json').write_text(json.dumps(record, indent=2) + '\n')
        candidate.rename(destination)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({'status': result['status'], 'source_files': len(result['source_files'])}))
