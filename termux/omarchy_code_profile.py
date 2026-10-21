"""Export original desktop customizations once; never mutate either live profile."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from omarchy_code_web import exclusive, private_dir, read_private

SOURCE = Path('/opt/loopy-vscode/1.141.0/data/user-data/User')
LIMIT = 2 * 1024 * 1024


def content(path):
    if not os.path.lexists(path): return None
    if path.is_symlink(): raise ValueError('profile-source-symlink')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
        raise ValueError('profile-source-bounds')
    return path.read_text()


def export_profile(source, output):
    source, output = Path(source), private_dir(output)
    if source.is_symlink() or not source.is_dir(): raise ValueError('profile-source-invalid')
    settings, keys = content(source / 'settings.json'), content(source / 'keybindings.json')
    snippets, total = {}, 0
    directory = source / 'snippets'
    if directory.is_symlink(): raise ValueError('profile-snippets-symlink')
    if directory.exists():
        for path in sorted(directory.rglob('*')):
            if path.is_symlink(): raise ValueError('profile-snippet-symlink')
            if path.is_dir(): continue
            if path.suffix not in ('.json', '.code-snippets'): continue
            text = content(path)
            total += len(text.encode())
            if total > LIMIT or len(snippets) >= 256: raise ValueError('profile-snippets-bounds')
            snippets[str(path.relative_to(directory))] = text
    template = {'name': 'Loopy Omarchy',
                'settings': json.dumps({'settings': settings}),
                'keybindings': json.dumps({'keybindings': keys, 'platform': 2}),
                'snippets': json.dumps({'snippets': snippets})}
    payload = (json.dumps(template, ensure_ascii=False, indent=2) + '\n').encode()
    if len(payload) > 4 * LIMIT: raise ValueError('profile-export-bounds')
    digest = hashlib.sha256(payload).hexdigest()
    target = output / ('loopy-omarchy-' + digest[:16] + '.code-profile')
    try: exclusive(target, payload)
    except FileExistsError:
        if read_private(target, 4 * LIMIT) != payload: raise ValueError('profile-export-collision')
    # A separate exact settings copy is available for reviewed Remote Machine merge.
    # Export does not claim browser import or apply machine settings automatically.
    if settings is not None:
        snapshot = output / ('desktop-settings-' + digest[:16] + '.json')
        try: exclusive(snapshot, settings.encode())
        except FileExistsError:
            if read_private(snapshot, LIMIT) != settings.encode(): raise ValueError('profile-settings-collision')
    return target


def main():
    try:
        if len(sys.argv) != 1: raise ValueError('profile-export-arguments')
        result = export_profile(SOURCE, Path.home() / '.local/share/loopy-code-web/profile-import')
        print(str(result))  # Path only; never print settings, tokens, or extension state.
        return 0
    except (OSError, ValueError):
        print('Code profile export unavailable; original settings were not modified.', file=sys.stderr)
        return 1
