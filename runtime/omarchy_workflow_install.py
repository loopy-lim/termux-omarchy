"""Install the pinned personal shell, terminal bindings and TUI/remote entries."""
import argparse
import json
import os
from pathlib import Path

import omarchy_guest_install as guest

COMPONENT = guest.Component(
    '3555aa327cbb1327bb5a167b208b894c44c74bfa3065844d5f8560b603a3d486', 71680,
    'f4cc517629fe3f084a29ef519a0c2458ecde87b92ada5f229291fe0809024fd4', 2672,
    'guest-personal-workflow', 'workflow-install.json', (
        ('home/omarchy/.config/foot/foot.ini', 0o644),
        ('home/omarchy/.config/hypr/bindings.lua', 0o644),
        ('home/omarchy/.config/tmux/tmux.conf', 0o644),
        ('usr/share/omarchy/bin/omarchy-launch-tui', 0o755),
    ))


def validate(payload, manifest):
    return guest.Payload(payload, manifest, component=COMPONENT)


def install(payload, manifest, home, prefix):
    return guest.install(payload, manifest, home, prefix, component=COMPONENT)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install pinned Omarchy personal and remote workflow')
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(install(args.payload, args.manifest, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))


if __name__ == '__main__':
    main()
