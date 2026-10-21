"""Rasterize pinned public icons into GTK raw caches; decoder policy stays intact."""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile

DIRECTORY = '32x32/icons'
FORMAT = 'GTK3 icon cache 1.0 / raw RGBA GdkPixdata'
NAME = re.compile(r'[A-Za-z0-9_.+-]{1,180}\Z')
PREFIXES = {'Adwaita': 'usr/share/icons/Adwaita/', 'hicolor': 'usr/share/icons/hicolor/'}
GTK_VERSION = '3.24.52'
GTK_REFERENCES = {
    'gtkiconcache.c': 'c20e901dcf4c45ddb0fb6326b12dbd8d8567d16f958c91f70399f40c3584b198',
    'gtkicontheme.c': '1b76c76d15216ddee41893a1c4f6ca2161c3128ca33935c7f5c6e07c266b3275',
    'encodesymbolic.c': '25987ce4ff9476aa1df2607be23c7da235a9dd262650d758262185462deced35',
    'gtkiconcachevalidator.c': 'eea9fbbf42af8094ad6d29e08814e55986f1599ad338ab17e009245d1b5754ad',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def word(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def string(value):
    data = value.encode() + b'\0'
    return data + bytes(-len(data) % 4)


def name_hash(name):
    value = ord(name[0])
    for char in name[1:]:
        value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
    return value


def cache_bytes(images):
    if not images or len(images) > 2000:
        raise ValueError('Bounded trusted icon set required')
    entries = {}
    for name, (pixels, symbolic) in images.items():
        if not NAME.fullmatch(name) or len(pixels) != 4096 or type(symbolic) is not bool:
            raise ValueError('Fixed trusted icon name and 32x32 RGBA pixels required')
        for alias in ((name, name + '.symbolic') if symbolic else (name,)):
            if alias in entries:
                raise ValueError('Icon alias collision')
            entries[alias] = pixels
    buckets = [[] for _ in range(257)]
    for name in sorted(entries):
        buckets[name_hash(name) % 257].append(name)
    segments, heads = [], []
    offset = 12 + 4 + 4 * len(buckets)
    for bucket in buckets:
        heads.append(offset if bucket else 0xFFFFFFFF)
        for position, name in enumerate(bucket):
            encoded = string(name)
            listing = offset + 12 + len(encoded)
            image = listing + 12
            pixel = image + 8
            pixdata = word(0x47646B50, 4120, 0x01010002, 128, 32, 32) + entries[name]
            size = 12 + len(encoded) + 12 + 8 + 8 + len(pixdata)
            next_node = offset + size if position + 1 < len(bucket) else 0xFFFFFFFF
            segment = word(next_node, offset + 12, listing) + encoded
            segment += word(1) + struct.pack('>HHI', 0, 4, image)
            segment += word(pixel, 0, 0, len(pixdata)) + pixdata
            segments.append(segment)
            offset += size
    data = struct.pack('>HHII', 1, 0, 12, offset) + word(257, *heads)
    data += b''.join(segments) + word(1, offset + 8) + string(DIRECTORY)
    if cache_pixels(data) != entries:
        raise ValueError('Raw cache failed roundtrip')
    return data


def cache_pixels(data):
    def unpack(fmt, offset):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(data):
            raise ValueError('Cache offset exceeds trusted data')
        return struct.unpack_from(fmt, data, offset)
    def text(offset):
        if offset < 12 or offset >= len(data):
            raise ValueError('Cache name offset differs')
        end = data.find(b'\0', offset, offset + 200)
        if end < 0:
            raise ValueError('Cache name is unterminated')
        value = data[offset:end].decode('ascii')
        if not NAME.fullmatch(value):
            raise ValueError('Cache name differs')
        return value
    if len(data) > 20 * 1024**2 or unpack('>HHI', 0) != (1, 0, 12):
        raise ValueError('Trusted GTK cache header required')
    directory = unpack('>I', 8)[0]
    if unpack('>II', directory) != (1, directory + 8) \
            or data[directory + 8:] != string(DIRECTORY):
        raise ValueError('Complete fixed icon directory required')
    count = unpack('>I', 12)[0]
    if count != 257:
        raise ValueError('Trusted cache hash table differs')
    entries, seen = {}, set()
    for bucket in range(count):
        offset = unpack('>I', 16 + 4 * bucket)[0]
        while offset != 0xFFFFFFFF:
            if offset in seen or len(seen) >= 4000:
                raise ValueError('Cache chain duplicates or cycles')
            seen.add(offset)
            following, name_offset, listing = unpack('>III', offset)
            name = text(name_offset)
            if name in entries or name_hash(name) % count != bucket:
                raise ValueError('Cache hash membership differs')
            if unpack('>IHH', listing) != (1, 0, 4):
                raise ValueError('Trusted PNG cache member required')
            image = unpack('>I', listing + 8)[0]
            pixel, metadata = unpack('>II', image)
            if metadata != 0 or unpack('>II', pixel) != (0, 4120) \
                    or unpack('>IIIIII', pixel + 8) != (0x47646B50, 4120, 0x01010002, 128, 32, 32):
                raise ValueError('Fixed uncompressed trusted RGBA required')
            start = pixel + 32
            if start + 4096 > directory:
                raise ValueError('Cache pixels exceed their bounds')
            entries[name] = data[start:start + 4096]
            offset = following
    if not entries:
        raise ValueError('Empty icon cache')
    return entries


def icon_files(files, prefix):
    result = {}
    for name, entry in files.items():
        if not name.startswith(prefix) or not name.endswith(('.svg', '.png')):
            continue
        if entry['kind'] == 'file': result[name] = entry
        elif entry['kind'] == 'symlink':
            target = entry['target']; original = files.get(target, {})
            if not target.startswith(prefix) or original.get('kind') != 'file':
                raise ValueError('Trusted stock icon alias redirects')
            result[name] = dict(original, resolved_source=target)
    return result


def remote_icon_files(files):
    return icon_files({name: entry for name, entry in files.items()
                       if 'remmina' in entry.get('owners', [])}, PREFIXES['hicolor'])


def checked_icons(receipt, files, base_files, caches=None):
    if receipt.get('schema') != 1 or receipt.get('format') != FORMAT \
            or receipt.get('decoder_policy_changed') is not False \
            or receipt.get('external_images_accepted') is not False:
        raise ValueError('Trusted raw icon provenance required')
    themes = receipt.get('themes', {})
    if not themes or not set(themes) <= set(PREFIXES):
        raise ValueError('Scoped trusted icon themes required')
    source_names = set()
    decoded = {theme: cache_pixels(data) for theme, data in (caches or {}).items()}
    originals = {'Adwaita': icon_files(base_files, PREFIXES['Adwaita']),
                 'hicolor': remote_icon_files(files)}
    for theme, identity in themes.items():
        for name, key in (('icon-theme.cache', 'cache_sha256'), ('index.theme', 'index_sha256')):
            entry = files.get(PREFIXES[theme] + name, {})
            if entry.get('kind') != 'file' or entry.get('sha256') != identity.get(key):
                raise ValueError('Trusted icon theme member differs')
    for record in receipt.get('sources', []):
        theme, name = record['theme'], record['source']
        if theme not in themes:
            raise ValueError('Untrusted icon source theme')
        original = originals[theme].get(name, {})
        if name in source_names or not name.startswith(PREFIXES[theme]) \
                or original.get('kind') != 'file' or original.get('sha256') != record['source_sha256']:
            raise ValueError('Icon source differs from signed manifest')
        source_names.add(name)
        if 'raster_path' in record:
            entry = files.get(record['raster_path'], {})
            if not record['raster_path'].startswith(PREFIXES[theme] + DIRECTORY + '/') \
                    or entry.get('kind') != 'file' or entry.get('sha256') != record['raster_sha256']:
                raise ValueError('Derived trusted raster differs')
            if caches is not None:
                pixels = decoded[theme].get(record['name'])
                if pixels is None or sha(pixels) != record['rgba_sha256'] \
                        or record['symbolic'] and decoded[theme].get(record['name'] + '.symbolic') != pixels:
                    raise ValueError('Raw cache pixels differ from source-bound raster')
    if not source_names:
        raise ValueError('Trusted icon sources required')
    return source_names


def extract_sources(archive, identities, destination):
    found = set()
    with tarfile.open(archive, 'r|*') as reader:
        for member in reader:
            if member.name not in identities:
                continue
            expected = identities[member.name]
            if member.name in found or not member.isfile() or member.size != expected['size']:
                raise ValueError('Trusted source icon type or size differs')
            data = reader.extractfile(member).read()
            if sha(data) != expected['sha256']:
                raise ValueError('Trusted source icon bytes differ')
            path = destination / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            found.add(member.name)
    if found != set(identities):
        raise ValueError('Complete trusted source icon set required')


def generate(root, output, renderer='/opt/homebrew/bin/rsvg-convert'):
    from PIL import Image
    from .omarchy_catalog import BUNDLE
    from .omarchy_rootfs import digest_file
    root, output = Path(root), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('Preserve the previous trusted icon candidate')
    output.mkdir(parents=True)
    base = root / BUNDLE
    base_receipt = json.loads((base / 'receipt.json').read_text())
    base_files = json.loads((base / 'manifest.json').read_text())['files']
    remote = root / 'build/omarchy-remote/client-bundle'
    remote_files = json.loads((remote / 'manifest.json').read_text())['files']
    sources = {'Adwaita': icon_files(base_files, PREFIXES['Adwaita']),
               'hicolor': remote_icon_files(remote_files)}
    source_root = output / 'sources'
    base_sources = {identity.get('resolved_source', name): identity
                    for name, identity in sources['Adwaita'].items()}
    extract_sources(base / base_receipt['archive'], base_sources, source_root)
    extract_sources(remote / 'rootfs.tar.gz', sources['hicolor'], source_root)
    producer = Path(renderer).resolve()
    version = subprocess.run([str(producer), '--version'], check=True, capture_output=True, text=True).stdout
    records, extras, themes = [], {}, {}
    styles = []
    for plane in range(3):
        css = 'rect,circle,path {fill:rgb(0,255,0) !important;}\n'
        for index, role in enumerate(('success', 'warning', 'error')):
            color = '255,0,0' if index == plane else '0,255,0'
            css += '.' + role + ' {fill:rgb(' + color + ') !important;}\n'
        path = output / ('mask-' + str(plane) + '.css'); path.write_text(css); styles.append(path)
    def render(item):
        theme, name, identity = item
        source = source_root / identity.get('resolved_source', name)
        icon_name = Path(name).stem
        symbolic = icon_name.endswith(('-symbolic', '-symbolic-ltr', '-symbolic-rtl'))
        def raster(plane=None):
            if source.suffix == '.png':
                return Image.open(source).convert('RGBA').resize((32, 32), Image.Resampling.LANCZOS)
            command = [str(producer), '--width', '32', '--height', '32']
            if plane is not None: command += ['--stylesheet', str(styles[plane])]
            command.append(str(source))
            run = subprocess.run(command, check=True, capture_output=True, timeout=20)
            return Image.open(io.BytesIO(run.stdout)).convert('RGBA')
        if symbolic and source.suffix == '.svg':
            masks = [raster(plane) for plane in range(3)]
            image = Image.merge('RGBA', (masks[0].getchannel('R'), masks[1].getchannel('R'),
                                        masks[2].getchannel('R'), masks[0].getchannel('A')))
        else:
            image = raster(); symbolic = False
        pixels = image.tobytes()
        if image.size != (32, 32): raise ValueError('Fixed trusted raster dimensions required')
        return theme, icon_name, symbolic, pixels, name, identity
    jobs = [(theme, name, identity) for theme in sources for name, identity in sorted(sources[theme].items())]
    selected = {theme: {} for theme in sources}
    # Prefer vector/high resolution sources when a stock name occurs at several sizes.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for theme, name, symbolic, pixels, source, identity in pool.map(render, jobs):
            record = {'source': source, 'source_sha256': identity['sha256'], 'theme': theme,
                      'name': name, 'symbolic': symbolic, 'rgba_sha256': sha(pixels)}
            records.append(record)
            rank = (source.endswith('.svg'), identity['size'])
            if name not in selected[theme] or rank > selected[theme][name][0]:
                selected[theme][name] = (rank, pixels, symbolic, record)
    for theme, icons in selected.items():
        directory = output / 'share/icons' / theme / DIRECTORY
        directory.mkdir(parents=True)
        images = {}
        for name, (_, pixels, symbolic, record) in sorted(icons.items()):
            filename = name + ('.symbolic.png' if symbolic else '.png')
            path = directory / filename
            Image.frombytes('RGBA', (32, 32), pixels).save(path)
            record.update(raster_path='usr/share/icons/' + theme + '/' + DIRECTORY + '/' + filename,
                          raster_sha256=digest_file(path))
            extras[record['raster_path']] = path
            images[name] = (pixels, symbolic)
        theme_root = directory.parent.parent
        index = theme_root / 'index.theme'
        inheritance = '\nInherits=hicolor' if theme == 'Adwaita' else ''
        index.write_text('[Icon Theme]\nName=' + theme + inheritance + '\nDirectories=' + DIRECTORY + '\n\n'
                         '[' + DIRECTORY + ']\nSize=32\nType=Scalable\nMinSize=8\nMaxSize=256\nContext=Actions\n')
        cache = theme_root / 'icon-theme.cache'; cache.write_bytes(cache_bytes(images))
        for path in (index, cache):
            extras['usr/share/icons/' + theme + '/' + path.name] = path
        themes[theme] = {'icons': len(images), 'entries': len(cache_pixels(cache.read_bytes())),
                         'cache_sha256': digest_file(cache), 'index_sha256': digest_file(index)}
    receipt = {'schema': 1, 'format': FORMAT, 'base_archive_sha256': base_receipt['archive_sha256'],
               'base_manifest_sha256': digest_file(base / 'manifest.json'),
               'remote_source_manifest_sha256': digest_file(remote / 'manifest.json'),
               'producer_sha256': digest_file(Path(__file__)), 'renderer_sha256': digest_file(producer),
               'renderer_version': version, 'pillow_version': Image.__version__,
               'render_options': ['--width', '32', '--height', '32'],
               'gtk_version': GTK_VERSION, 'gtk_reference_sources': GTK_REFERENCES,
               'gtk_reference_url': 'https://github.com/GNOME/gtk/tree/' + GTK_VERSION + '/gtk',
               'symbolic_algorithm': 'GTK3.24.52 encodesymbolic three red-channel passes',
               'mask_stylesheets': [digest_file(path) for path in styles], 'themes': themes, 'sources': records,
               'decoder_policy_changed': False, 'external_images_accepted': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return extras, receipt
