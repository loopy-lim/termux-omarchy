#!/usr/bin/env python3
"""Publish only the approved separate watchdog asset; preserve all existing destinations."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
try:
    from tools.omarchy_watchdog_v4_inputs import CANDIDATE, candidate_inputs, checked_inputs, provenance
except ModuleNotFoundError:
    from omarchy_watchdog_v4_inputs import CANDIDATE, candidate_inputs, checked_inputs, provenance

ROOT = Path(__file__).resolve().parents[1]


def publish(root):
    root = Path(root).absolute()
    destination = root / 'android/assets/omarchy-watchdog-v4'
    if destination.exists() or destination.is_symlink():
        raise ValueError('Refuse to replace existing watchdog assets')
    if destination.parent.resolve() != root.resolve() / 'android/assets':
        raise ValueError('Refuse redirected watchdog asset parent')
    candidate_inputs(root)
    record = provenance(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.watchdog-asset-', dir=destination.parent) as folder:
        staged = Path(folder) / 'assets'; staged.mkdir()
        shutil.copyfile(root / CANDIDATE / 'components/start-hyprland', staged / 'start-hyprland')
        shutil.copyfile(root / CANDIDATE / 'candidate-source/LICENSE', staged / 'LICENSE')
        shutil.copyfile(root / CANDIDATE / 'glaze-source/LICENSE', staged / 'Glaze-LICENSE')
        (staged / 'provenance.json').write_text(json.dumps(record, indent=2) + '\n')
        # Exclusive directory creation owns the final path before any file publication.
        destination.mkdir()
        for path in staged.iterdir(): os.link(path, destination / path.name)
    checked_inputs(root)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    args = parser.parse_args(); record = publish(args.project_root)
    print(json.dumps({'sha256': record['binary_sha256'], 'bytes': record['binary_bytes'], 'physical_device': False}))


if __name__ == '__main__': main()
