"""Build-time authentication of the separate Arch remote client payload and helpers."""
import hashlib
import json
from pathlib import Path
import tarfile

try:
    from .prepare_omarchy_remote import ASSET, PROVENANCE, INVENTORY, TRANSACTION, SIGNER, inventory_text
    from .omarchy_catalog import BUNDLE
    from .omarchy_rootfs import digest_file
    from .omarchy_remote_elf import needed, resolve_library
    from .omarchy_remote_icons import checked_icons, icon_files, remote_icon_files, PREFIXES, GTK_VERSION, GTK_REFERENCES
except ImportError:
    from prepare_omarchy_remote import ASSET, PROVENANCE, INVENTORY, TRANSACTION, SIGNER, inventory_text
    from omarchy_catalog import BUNDLE
    from omarchy_rootfs import digest_file
    from omarchy_remote_elf import needed, resolve_library
    from omarchy_remote_icons import checked_icons, icon_files, remote_icon_files, PREFIXES, GTK_VERSION, GTK_REFERENCES


def checked_sources(root):
    root = Path(root); paths = []
    for name in ('remote_connections.py', 'remote_desktop.py'):
        source = root / 'guest/desktop/usr/local/lib/loopy' / name
        asset = root / 'android/assets/omarchy-bridge' / name
        if any(path.is_symlink() or not path.is_file() for path in (source, asset)) \
                or source.read_bytes() != asset.read_bytes():
            raise ValueError('Generated Omarchy remote helper differs from canonical source: ' + name)
        paths.extend((source, asset))
    return paths


def checked_inputs(root):
    root = Path(root); paths = checked_sources(root)
    archive, provenance, inventory = root / ASSET, root / PROVENANCE, root / INVENTORY
    for path, maximum in ((archive, 16 * 1024**2), (provenance, 2 * 1024**2), (inventory, 1024**2)):
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise ValueError('Bounded regular Omarchy remote client input required')
    receipt = json.loads(provenance.read_text())
    key = root / 'third_party/omarchy-remote-signing-key.asc'
    base_receipt = root / BUNDLE / 'receipt.json'; base_manifest = root / BUNDLE / 'manifest.json'
    if receipt.get('schema') != 1 or receipt.get('archive_sha256') != digest_file(archive) \
            or receipt.get('archive_bytes') != archive.stat().st_size \
            or receipt.get('base_archive_sha256') != json.loads(base_receipt.read_text())['archive_sha256'] \
            or receipt.get('base_manifest_sha256') != digest_file(base_manifest) \
            or receipt.get('base_transaction_sha256') != digest_file(root / TRANSACTION) \
            or receipt.get('signing_key_sha256') != digest_file(key) \
            or receipt.get('signing_key_fingerprint') != SIGNER or receipt.get('package_scripts_executed') is not False \
            or receipt.get('selected_plugins') != ['RDP', 'VNC']:
        raise ValueError('Omarchy remote client provenance differs')
    packages = receipt['added_packages']; signatures = receipt['verified_signatures']
    if len(packages) != 9 or len(signatures) != len(packages) \
            or {p['name']: p['sha256'] for p in packages} != {p['name']: p['sha256'] for p in signatures} \
            or any(p['signer'] != SIGNER for p in signatures):
        raise ValueError('Complete officially signed remote package transaction required')
    manifest = root / 'build/omarchy-remote/client-bundle/manifest.json'
    if digest_file(manifest) != receipt['manifest_sha256']:
        raise ValueError('Remote inventory manifest identity differs')
    files = json.loads(manifest.read_text())['files']
    base_files = json.loads(base_manifest.read_text())['files']
    icons = receipt.get('trusted_icons', {})
    if set(icons.get('themes', {})) != {'Adwaita', 'hicolor'} \
            or icons.get('producer_sha256') != digest_file(root / 'tools/omarchy_remote_icons.py') \
            or icons.get('gtk_version') != GTK_VERSION or icons.get('gtk_reference_sources') != GTK_REFERENCES \
            or icons.get('base_archive_sha256') != receipt['base_archive_sha256'] \
            or icons.get('base_manifest_sha256') != receipt['base_manifest_sha256']:
        raise ValueError('Source-bound trusted icon caches required')
    expected_sources = set(icon_files(base_files, PREFIXES['Adwaita']))
    expected_sources.update(remote_icon_files(files))
    if checked_icons(icons, files, base_files) != expected_sources:
        raise ValueError('Complete signed stock and Remmina icon sources required')
    if inventory.read_bytes() != inventory_text(receipt, files):
        raise ValueError('Remote client runtime inventory differs')
    actual = {}; total = 0; caches = {}
    with tarfile.open(archive, 'r|gz') as reader:
        for member in reader:
            entry = files.get(member.name)
            if member.name in actual or entry is None or member.mode != entry['mode']:
                raise ValueError('Remote client archive entry identity differs')
            if member.isfile():
                native = (member.name == 'usr/bin/remmina' or member.name.startswith(('usr/lib/', 'loopy-remmina/'))) \
                         and not member.name.startswith('usr/lib/remmina/plugins/')
                trusted_cache = member.name in ('usr/share/icons/Adwaita/icon-theme.cache',
                                                'usr/share/icons/hicolor/icon-theme.cache')
                content = reader.extractfile(member).read() if native or trusted_cache else None
                actual_sha = hashlib.sha256(content).hexdigest() if content is not None else \
                             hashlib.file_digest(reader.extractfile(member), 'sha256').hexdigest()
                if entry['kind'] != 'file' or member.size != entry['size'] \
                        or actual_sha != entry['sha256']:
                    raise ValueError('Remote client payload bytes differ')
                total += member.size
                if trusted_cache:
                    caches[member.name.split('/')[3]] = content
                if native:
                    for library in needed(content) or []:
                        resolve_library(library, files, base_files)
            elif member.isdir():
                if entry['kind'] != 'directory': raise ValueError('Remote entry type differs')
            elif member.issym():
                if entry['kind'] != 'symlink' or member.linkname != entry['link']:
                    raise ValueError('Remote library symlink differs')
            else: raise ValueError('Unsupported remote client archive member')
            actual[member.name] = entry
    if actual != files or total != receipt['materialized_bytes']:
        raise ValueError('Remote client full inventory or materialized bytes differ')
    checked_icons(icons, files, base_files, caches)
    paths.extend((archive, provenance, inventory, key, base_receipt, base_manifest, root / TRANSACTION, manifest))
    paths.extend(root / name for name in ('tools/prepare_omarchy_remote.py', 'tools/omarchy_remote_inputs.py',
        'tools/arch_vercmp.py', 'tools/omarchy_remote_elf.py', 'tools/omarchy_remote_icons.py',
        'third_party/pacman-vercmp/version.c', 'third_party/pacman-vercmp/LICENSE'))
    return paths
