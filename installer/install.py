#!/usr/bin/env python3
"""Inspect the developer alpha; refuse installation without a published binary closure."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from verify import validate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--check', action='store_true', help='verify source and list unmet prerequisites')
    operation.add_argument('--apply', action='store_true', help='unavailable in this source-only alpha')
    parser.add_argument('--bundle', type=Path, help='reserved for the reviewed future payload installer')
    args = parser.parse_args(argv)
    try:
        source = validate()
    except (OSError, ValueError, KeyError, TypeError, SyntaxError):
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': 'source-verification-failed',
                          'deviceChangesRequested': False}, sort_keys=True))
        return 1
    # Do not inspect HOME, open --bundle, import runtime modules, fetch, or install.
    # Publishing hashes of historical payloads does not make them a complete release.
    result = {'schema': 1, 'status': 'source-only-developer-alpha',
              'automaticInstallEnabled': False, 'binaryClosureComplete': False,
              'fullFreshInstallVerified': False, 'deviceChangesRequested': False,
              'source': {name: value for name, value in source.items()
                         if name not in ('missing', 'upstreamBundle')},
              'missing': source['missing'], 'upstreamBundle': source['upstreamBundle']}
    if args.apply:
        result.update(status='blocked', reason='binary-closure-unavailable')
    print(json.dumps(result, sort_keys=True))
    return 2 if args.apply else 0


if __name__ == '__main__':
    raise SystemExit(main())
