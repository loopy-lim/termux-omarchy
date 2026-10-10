"""Install the pinned personal shell, terminal bindings and TUI/remote entries."""
import argparse
import json
import os
from pathlib import Path

import omarchy_guest_install as guest

COMPONENT = guest.Component(
    'ebc2f5494c290b88ebcb0979e8a51bf7310c6ecfb200ae1188d74e2a909ea73b', 61440,
    '0db92c0f318d9bd3ade54649c066c3f9c396bac8b62d42f296bc8201407e3099', 3213,
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
