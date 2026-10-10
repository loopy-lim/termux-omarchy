"""One command for pinned native components, adapters and personal workflow."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

import omarchy_install as base
import omarchy_host_install as host
import omarchy_guest_install as guest
import omarchy_workflow_install as workflow
import omarchy_tools_install as tools
import omarchy_proot_install as proot
import omarchy_input_install as korean
import omarchy_machine_id as machine_id


def existing_runtime(home, prefix, sources):
    """A fresh setup never upgrades or fills gaps in an existing runtime."""
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    fd, locks = base.walk(home, '.local/share/loopy-omarchy'), []
    if fd is None:
        return False
    try:
        installed = machine_id.context(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'):
            locks.append(machine_id.lock_existing(fd, name))
        machine_id.context(root, fd, home, prefix, installed)
        base.require(installed.get('runtime_files') == base.RUNTIME_SHA and not sources.missing(fd),
                     'setup-existing-runtime-incomplete')
        proot.stopped(fd)
        base.require(not any(name.startswith(proot.STAGE_PREFIX) for name in os.listdir(fd)),
                     'proot-install-partial')
        proot.guard.selection(root)
        return True
    finally:
        for lock in reversed(locks): os.close(lock)
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepare the pinned Termux Omarchy native components')
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--sources', type=Path, default=Path(__file__).parent)
    parser.add_argument('--weston-payload', type=Path, default=Path(__file__).parent / 'payload.tar')
    parser.add_argument('--weston-manifest', type=Path, default=Path(__file__).parent / 'payload-manifest.json')
    parser.add_argument('--guest-payload', type=Path, default=Path(__file__).parent / 'guest-payload.tar')
    parser.add_argument('--guest-manifest', type=Path, default=Path(__file__).parent / 'guest-manifest.json')
    parser.add_argument('--workflow-payload', type=Path, default=Path(__file__).parent / 'workflow-payload.tar')
    parser.add_argument('--workflow-manifest', type=Path, default=Path(__file__).parent / 'workflow-manifest.json')
    parser.add_argument('--tools-dir', type=Path, default=Path(__file__).parent)
    parser.add_argument('--proot-dir', type=Path, default=Path(__file__).parent / 'proot-guard')
    parser.add_argument('--input-dir', type=Path, default=Path(__file__).parent / 'korean-input')
    parser.add_argument('--input-payload', type=Path, default=Path(__file__).parent / 'input-config-payload.tar')
    parser.add_argument('--input-manifest', type=Path, default=Path(__file__).parent / 'input-config-manifest.json')
    args = parser.parse_args(argv)
    stage = 'host-validation'
    try:
        payload = host.Payload(args.weston_payload, args.weston_manifest)
        payload.close()
        stage = 'runtime-validation'
        sources = base.RuntimeSources(args.sources)
        stage = 'guest-validation'
        guest.Payload(args.guest_payload, args.guest_manifest)
        stage = 'workflow-validation'
        workflow.validate(args.workflow_payload, args.workflow_manifest)
        stage = 'tools-validation'
        tools.validate(args.tools_dir)
        stage = 'proot-validation'
        proot.source_files(args.proot_dir)
        stage = 'input-validation'
        input_source = korean.validate(args.input_dir, args.input_payload, args.input_manifest)
        home, prefix = os.environ['HOME'], os.environ['PREFIX']
        stage = 'existing-runtime-validation'
        if existing_runtime(home, prefix, sources):
            stage = 'existing-input-validation'
            korean.preflight_targets(input_source, home, prefix)
        stage = 'base-installation'
        installed = base.install(args.bundle, home, prefix, sources=args.sources)
        stage = 'proot-installation'
        guarded = proot.install(args.proot_dir, home, prefix)
        stage = 'host-installation'
        native = host.install(args.weston_payload, args.weston_manifest, home, prefix)
        stage = 'guest-installation'
        adapters = guest.install(args.guest_payload, args.guest_manifest, home, prefix)
        stage = 'machine-id-installation'
        machine = machine_id.install(home, prefix)
        stage = 'tools-installation'
        developer = tools.install(args.tools_dir, home, prefix)
        stage = 'workflow-installation'
        personal = workflow.install(args.workflow_payload, args.workflow_manifest, home, prefix)
        stage = 'input-installation'
        ime = korean.install(args.input_dir, args.input_payload, args.input_manifest, home, prefix)
        print(json.dumps({'schema': 1, 'status': 'installed-components', 'base': installed,
                          'weston': native, 'guest': adapters, 'tools': developer, 'workflow': personal,
                          'prootGuard': guarded, 'machineID': machine, 'input': ime,
                          'fullDesktopConfigured': False}, sort_keys=True))
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) else 'setup-unavailable'
        print(json.dumps({'schema': 1, 'status': 'failed', 'stage': stage, 'reason': reason}, sort_keys=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
