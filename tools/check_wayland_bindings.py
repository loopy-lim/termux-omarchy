#!/usr/bin/env python3
"""Check registry version negotiation in an owned WAYLAND_DEBUG fixture trace.

Reports only public protocol names and versions; no keys, clipboard or pixels.
Passing proves version negotiation only, not rendering or a usable desktop.
"""
import argparse
import json
from pathlib import Path
import re

EVENT = re.compile(r'wl_registry[#@](\d+)\.(global|bind)\((\d+), "([a-zA-Z0-9_]+)", (\d+)')


def validate(trace):
    globals_, bindings, violations = {}, [], []
    for match in EVENT.finditer(trace):
        registry, action, identifier, interface, version = match.groups()
        version = int(version)
        key = registry, identifier, interface
        if action == 'global':
            globals_[key] = version
            continue
        advertised = globals_.get(key)
        binding = {'interface': interface, 'requested': version, 'advertised': advertised}
        bindings.append(binding)
        if advertised is None or not 1 <= version <= advertised:
            violations.append(binding)
    return {'valid': bool(bindings) and not violations, 'bindings': bindings,
            'violations': violations, 'evidence_boundary': 'Public registry versions only.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.trace.stat().st_size > 2 * 1024**2:
        raise SystemExit('Fixture trace exceeds its budget')
    result = validate(args.trace.read_text(errors='replace'))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(text + '\n')
    print(text)
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
