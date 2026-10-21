"""Bounded Arch ARM metadata and complete dependency transactions.

Pacman databases can split desc and depends. Never discard unavailable roots,
versioned SONAME providers or unresolved alternatives to produce a green lock.
"""
from collections import deque
import io
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
from urllib.parse import urlparse

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9@+_.-]*')
REQUIREMENT = re.compile(r'([A-Za-z0-9][A-Za-z0-9@+_.-]*)(?:(>=|<=|=|>|<)([^\s]+))?')
MAX_DATABASE = 32 * 1024 * 1024
MAX_METADATA = 64 * 1024 * 1024


class ResolutionError(ValueError):
    def __init__(self, unresolved, selected):
        self.unresolved = sorted(set(unresolved))
        self.selected = selected
        super().__init__('Unresolved Arch transaction: ' + ', '.join(self.unresolved))


def parse_fields(data):
    result = {}
    for block in data.decode('utf-8').strip().split('\n\n'):
        lines = block.splitlines()
        if not lines:
            continue
        if not re.fullmatch(r'%[A-Z0-9_]+%', lines[0]):
            raise ValueError('Invalid Pacman metadata field')
        name = lines[0][1:-1]
        if name in result:
            raise ValueError('Duplicate Pacman metadata field')
        result[name] = lines[1:]
    return result


def parse_database(data, repository, base_url, *, rejected=None):
    if len(data) > MAX_DATABASE or urlparse(base_url).scheme != 'https':
        raise ValueError('Unbounded database or non-HTTPS package repository')
    records, invalid, seen, total = {}, {}, set(), 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe repository member path')
            if member.isdir():
                continue
            if not member.isfile() or len(path.parts) != 2 or path.name not in ('desc', 'depends'):
                raise ValueError('Unexpected repository member')
            minimum_size = 0 if path.name == 'depends' else 1
            if member.name in seen or not minimum_size <= member.size <= 256 * 1024:
                raise ValueError('Duplicate or unbounded repository member')
            seen.add(member.name); total += member.size
            if total > MAX_METADATA or len(seen) > 60000:
                raise ValueError('Repository metadata budget exceeded')
            try:
                fields = parse_fields(archive.extractfile(member).read())
            except (UnicodeDecodeError, ValueError) as error:
                if rejected is None:
                    raise
                invalid[path.parts[0]] = str(error)
                continue
            record = records.setdefault(path.parts[0], {})
            if record.keys() & fields.keys():
                raise ValueError('Duplicate split repository fields')
            record.update(fields)
    result, names = [], set()
    for directory, record in records.items():
        if directory in invalid:
            continue
        try:
            package = package_record(record, repository, base_url)
        except (ValueError, KeyError) as error:
            if rejected is None:
                raise
            invalid[directory] = str(error)
            continue
        if package['name'] in names:
            raise ValueError('Duplicate package name')
        names.add(package['name'])
        result.append(package)
    if rejected is not None:
        rejected.extend({'repository': repository, 'directory': directory, 'reason': reason}
                        for directory, reason in sorted(invalid.items()))
    return result


def package_record(record, repository, base_url):
    def one(key):
        values = record.get(key, [])
        if len(values) != 1:
            raise ValueError('Missing or ambiguous package field: ' + key)
        return values[0]
    name, version, architecture = one('NAME'), one('VERSION'), one('ARCH')
    filename, sha = one('FILENAME'), one('SHA256SUM')
    if not NAME.fullmatch(name) or architecture not in ('aarch64', 'any'):
        raise ValueError('Invalid package name or architecture')
    if not re.fullmatch(r'[A-Za-z0-9:+_.-]+', version):
        raise ValueError('Invalid package version')
    if PurePosixPath(filename).name != filename or not filename.startswith(name + '-') \
            or not re.fullmatch(r'[A-Za-z0-9@:+_.-]+\.pkg\.tar\.(xz|zst|gz)', filename):
        raise ValueError('Invalid package archive filename')
    if not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('Missing SHA256 package identity')
    compressed, installed = int(one('CSIZE')), int(one('ISIZE'))
    if not 0 < compressed <= 2 * 1024**3 or not 0 <= installed <= 8 * 1024**3:
        raise ValueError('Invalid package size budget')
    return {'name': name, 'version': version, 'architecture': architecture,
            'filename': filename, 'url': base_url.rstrip('/') + '/' + filename,
            'sha256': sha, 'size_bytes': compressed, 'installed_bytes': installed,
            'repository': repository, 'depends': record.get('DEPENDS', []),
            'provides': record.get('PROVIDES', []), 'conflicts': record.get('CONFLICTS', []),
            'license': record.get('LICENSE', []), 'signature': record.get('PGPSIG', [])}


def libalpm_compare(executable='vercmp'):
    cache = {}
    def compare(actual, required):
        key = actual, required
        if key not in cache:
            result = subprocess.run([executable, actual, required], capture_output=True,
                                    text=True, check=True, timeout=5)
            cache[key] = int(result.stdout.strip())
        return cache[key]
    return compare


def installed_records(installed):
    """Keep the actual local package versions and ABI providers as immutable inputs."""
    if not isinstance(installed, (list, tuple)) or len(installed) > 4096:
        raise ValueError('Invalid installed package inventory')
    result = {}
    for row in installed:
        if not isinstance(row, dict) or set(row) != {'name', 'version', 'provides', 'conflicts'} \
                or not isinstance(row['name'], str) or not NAME.fullmatch(row['name']) \
                or len(row['name']) > 128 or row['name'] in result \
                or not isinstance(row['version'], str) \
                or not re.fullmatch('[a-zA-Z0-9:+_.-]{1,127}', row['version']):
            raise ValueError('Invalid or duplicate installed package')
        for key in ('provides', 'conflicts'):
            if not isinstance(row[key], list) or len(row[key]) > 512 or any(
                    not isinstance(item, str) or len(item) > 255 or not REQUIREMENT.fullmatch(item)
                    for item in row[key]):
                raise ValueError('Invalid installed package ' + key)
        result[row['name']] = dict(row, depends=[])
    return result


def resolve(index, requested, *, preferences=None, compare=None, installed=()):
    """Resolve all requests; existing package names cannot be upgraded or replaced."""
    preferences, compare = preferences or {}, compare or libalpm_compare()
    local = installed_records(installed)
    by_name = dict(local)
    for package in index:
        by_name.setdefault(package['name'], package)
    providers = {}
    for package in by_name.values():
        for provided in [package['name'] + '=' + package['version'], *package['provides']]:
            match = REQUIREMENT.fullmatch(provided)
            if not match:
                raise ValueError('Invalid package provider: ' + provided)
            name, _, version = match.groups()
            providers.setdefault(name, []).append((package, version))

    def candidates(requirement):
        match = REQUIREMENT.fullmatch(requirement)
        if not match:
            raise ValueError('Invalid Arch requirement: ' + requirement)
        name, operator, required = match.groups()
        result = []
        for package, version in providers.get(name, []):
            if operator:
                if version is None:
                    continue
                order = compare(version, required)
                if not {'=': order == 0, '>=': order >= 0, '<=': order <= 0,
                        '>': order > 0, '<': order < 0}[operator]:
                    continue
            if package not in result:
                result.append(package)
        return name, result

    pending, selected, unresolved, examined = deque(requested), {}, [], set()
    while pending:
        requirement = pending.popleft()
        if requirement in examined:
            continue
        examined.add(requirement)
        name, choices = candidates(requirement)
        if any(p['name'] in local for p in choices):
            continue  # Any already-installed provider satisfies this exact requirement.
        held = [p for p in choices if p['name'] in selected]
        if held:
            continue
        exact = [p for p in choices if p['name'] == name]
        preferred = [p for p in choices if p['name'] == preferences.get(name)]
        choices = preferred or exact or choices
        if len(choices) != 1:
            unresolved.append(requirement)
            continue
        package = choices[0]
        if package['name'] not in selected:
            selected[package['name']] = package
            pending.extend(package['depends'])
    # Conflict matching uses the same ABI/version contract as dependency matching.
    active = {**local, **selected}
    for package in active.values():
        for conflict in package['conflicts']:
            _, choices = candidates(conflict)
            if any(p['name'] != package['name'] and p['name'] in active
                   and (package['name'] in selected or p['name'] in selected) for p in choices):
                unresolved.append(package['name'] + ' conflicts with ' + conflict)
    result = [selected[name] for name in sorted(selected)]
    if unresolved:
        raise ResolutionError(unresolved, result)
    return result
