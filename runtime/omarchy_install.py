"""Install one pinned Omarchy bundle without executing its installer or runtime.

Guest rootfs extraction belongs to reviewed PRoot-Distro 5.8/5.9.0; its absolute symlinks are
never extracted on the host here. An uncertain install is retained and refused.
"""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import uuid

CONTAINER = 'loopy-omarchy'
OUTER_BYTES = 1181941760
OUTER_SHA = '7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2'
FILE_SHA = {
    'BUNDLE-MANIFEST': '1eebd172b5b43657f819910bdafc905daf02df8a35dff5b40dac08000ee49c72',
    'rootfs.tar.xz': 'dbee00c0cb41f6b213c153ff4dc1c0898ba99dd0543ac13cef1601820366e2c5',
    'manifest/packages-aarch64-0.1.1.lock': '1d2935de23e434f37731052ba868e9833cba541afd517ff4e130c832d397b550',
    'host/bin/omarchy-process-guard': '49ce43ed5b20e1144588e0e6466bac6fe6a53537430d7bef94b3793ae18a98b1',
    'host/bin/omarchy-x11-keyboard': 'd4b1c844d6daab66134cb5c9699eafd47905f1a59724cf69dc191b7efa1984b0',
    'host/opt/weston/lib/libweston-14/x11-backend.so': '8cfb78a4a1a146596228c34f55562c3325c10bc355a5dff5f5765ca77093ea0e',
    'host/share/licenses/omarchy-android/LICENSE': '1285802f4c30eb389f65a9e0aadb307802778937e477b81423e1a7112b9fa867',
    'host/share/licenses/weston/COPYING': 'd4a8dc24555cbd8aa564147b537b792a103d2a3ecb6a80b2bf6494a0e6e19e34',
}
MANIFEST_FIELDS = {
    'format': '1', 'version': '0.1.1', 'architecture': 'aarch64', 'rootfs': 'rootfs.tar.xz',
    'components_lock_sha256': '4630710656d83b51c8fd6c80024f3c1977dc7c90f7ebf879baedb814c82abb77',
    'patches_lock_sha256': 'cc4394dbc47a43b5da7fb27e7084d9f2e8688c7138e6f9def493059dbde066ee',
    'artifacts_lock_sha256': 'eb1ffb44e115c5fac3ca3810ffef9143bcaaf7f764223c2dd5d34e3822b61159',
    'packages_lock_sha256': FILE_SHA['manifest/packages-aarch64-0.1.1.lock'],
    'host_artifact_sha256': '9dfabd5bb8bfcae7705aa90d5bad28414a12bf9e9b39337101f3ed92d4037fe4',
    'host_source_bundle_sha256': 'c1af9f82ab5c616f5fa7031f44b3ed17b1b07013169c9e19825b8131c057c1a1',
}
REQUIRED_PACKAGES = {'aquamarine': '0.14.0-2', 'hyprland': '0.56.1-3',
                     'mesa': '1:26.2.1-1', 'chromium': '151.0.7922.137-1', 'quickshell': '0.3.1-1'}
HOST_FILES = {
    'weston/x11-backend.so': 'host/opt/weston/lib/libweston-14/x11-backend.so',
    'licenses/omarchy-android/LICENSE': 'host/share/licenses/omarchy-android/LICENSE',
    'licenses/weston/COPYING': 'host/share/licenses/weston/COPYING',
}
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC
RUNTIME_SHA = {'omarchy_proot.py': 'b4be3b4d0bd2fe4cafb2a852e04a776803721a251ea455d410d3f3c1c57b5f52',
 'omarchy_commands.py': '81dd805e093d061f8159b2953fd2ebde553d90e10f31fe94412610e4ddc167fd',
 'omarchy.py': '304996e5d33c770a4d9cf2c28c6309bc0843af9d283b99a50d93d0e88707909f',
 'processes.py': 'fd9b51ebb267782ab4a5151298202b589f19f5bde2ebae6c515e16d484df7e5a',
 'omarchy_runtime.py': 'd209358f89c98ba91b8bfe2652a330058301dcee2951cc2328df29c3d20eaa5b',
 'omarchy_resources.py': '7cbdd53dd2c9ebbdc3a64cded5f6a52dcd3385a1f6f8cb3cce990b379b049e92',
 'omarchy_boot.py': '2966eeaf3b02c593a2638f2a13f0e3c069c43899e6da66b5bab37991b38f0203',
 'omarchy_input.py': 'baa102398d8b1525f5061eaccf27bad84b668d57e7875a59758eeda999df3389',
 'omarchy_audio.py': '3cebf98a8ee56f4b37a8edc2ccba8a481b303589d6dc4f188797f9309e7fe105',
 'omarchy_android.py': 'efb681f01380e55992838ca0178db801fc9ac06db3ec4ccb9c4216fad854584d',
 'omarchy_android_client.py': 'd564423e4ed197b88737662b0d8b90f61d65d34ba2ac3d467508ab5a64a63f9b'}


def require(value, code='omarchy-install-boundary'):
    if not value:
        raise ValueError(code)


def supported_proot_version(value):
    """5.9.0 retains the reviewed 5.8 install, argv and container layout APIs."""
    return isinstance(value, str) and re.fullmatch(r'(?:5\.8(?:\.[0-9]+)?|5\.9\.0)(?:-[0-9]+)?', value) is not None


def identity(row):
    return [row.st_dev, row.st_ino, row.st_uid]


def fingerprint(row):
    return identity(row) + [row.st_mode, row.st_size, row.st_mtime_ns, row.st_ctime_ns, row.st_nlink]


def directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    try:
        row = os.fstat(fd)
        require(row.st_uid == os.getuid() and not row.st_mode & 0o022)
        return fd
    except BaseException:
        os.close(fd)
        raise


def walk(base, relative, create=False):
    fd = directory(base)
    try:
        for part in PurePosixPath(relative).parts:
            require(part not in ('', '.', '..') and '/' not in part)
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                return None
            row = os.fstat(child)
            if row.st_uid != os.getuid() or row.st_mode & 0o022:
                os.close(child)
                raise ValueError('omarchy-install-parent')
            os.close(fd)
            fd = child
        result, fd = fd, None
        return result
    finally:
        if fd is not None:
            os.close(fd)


def regular(path, maximum, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=dir_fd)
    try:
        row = os.fstat(fd)
        require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid() and row.st_nlink == 1)
        require(not row.st_mode & 0o022 and 0 <= row.st_size <= maximum)
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def hashed(stream):
    value = hashlib.sha256()
    while True:
        data = stream.read(1024 * 1024)
        if not data:
            return value.hexdigest()
        value.update(data)


def publish(fd, temporary, name):
    """Publish without replacement; Android Python omits hard-link support."""
    if callable(getattr(os, 'link', None)):
        os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        return
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(fd, os.fsencode(temporary), fd, os.fsencode(name), 1) != 0:  # RENAME_NOREPLACE
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), name)


class RuntimeSources:
    """Reviewed native files only; never replace a different installed source."""
    def __init__(self, path):
        self.data, fd = {}, None
        try:
            fd = directory(path)
            for name, expected in RUNTIME_SHA.items():
                with regular(name, 131072, fd) as source:
                    before = fingerprint(os.fstat(source.fileno()))
                    data = source.read()
                    require(hashlib.sha256(data).hexdigest() == expected, 'omarchy-source-sha')
                    require(fingerprint(os.fstat(source.fileno())) == before, 'omarchy-source-changed')
                compile(data, name, 'exec')  # Syntax only; no module is executed.
                self.data[name] = data
        except OSError:
            raise ValueError('omarchy-source-filesystem') from None
        finally:
            if fd is not None:
                os.close(fd)

    def missing(self, root_fd):
        missing = []
        for name, expected in RUNTIME_SHA.items():
            try:
                os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                missing.append(name)
                continue
            with regular(name, 131072, root_fd) as current:
                require(hashed(current) == expected, 'omarchy-installed-source-changed')
        return missing

    def install(self, root_fd):
        missing = self.missing(root_fd)  # Validate every existing target before writing any file.
        if missing:
            try:
                with regular('runtime-state.json', 16384, root_fd) as source:
                    state = json.loads(source.read())
                require(state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True,
                        'omarchy-source-runtime-active')
            except FileNotFoundError:
                pass
        for name in missing:
            temporary = '.runtime-source-' + uuid.uuid4().hex
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW,
                         0o600, dir_fd=root_fd)
            with os.fdopen(fd, 'wb') as output:
                output.write(self.data[name]); output.flush(); os.fsync(output.fileno())
            try:
                publish(root_fd, temporary, name)
            finally:
                try:
                    os.unlink(temporary, dir_fd=root_fd)
                except FileNotFoundError:  # renameat2 moved the temporary entry.
                    pass
        os.fsync(root_fd)
        require(not self.missing(root_fd), 'omarchy-source-copy-incomplete')
        return dict(RUNTIME_SHA)


class Bundle:
    def __init__(self, path):
        self.file = regular(path, OUTER_BYTES)
        self.archive = None
        try:
            self.original = fingerprint(os.fstat(self.file.fileno()))
            require(self.original[4] == OUTER_BYTES and hashed(self.file) == OUTER_SHA, 'omarchy-bundle-sha')
            self.file.seek(0)
            self.archive = tarfile.open(fileobj=self.file, mode='r:')
            self.rows, total, names = {}, 0, set()
            allowed = set(FILE_SHA) | {'SHA256SUMS'}
            dirs = {'.'} | {str(p) for name in allowed for p in PurePosixPath(name).parents if str(p) != '.'}
            for index, row in enumerate(self.archive):
                require(index < 64)
                name = '.' if row.name in ('.', './') else (row.name[2:] if row.name.startswith('./') else row.name)
                require(not name.startswith('/') and '..' not in PurePosixPath(name).parts)
                require(name not in names and not row.linkname)
                names.add(name)
                if row.isdir():
                    require(name in dirs)
                    continue
                require(row.isreg() and name in allowed and row.size >= 0)
                total += row.size
                require(total <= OUTER_BYTES)
                self.rows[name] = row
            require(set(self.rows) == allowed)
            for name, want in FILE_SHA.items():
                with self.archive.extractfile(self.rows[name]) as data:
                    require(hashed(data) == want, 'omarchy-bundle-file-sha')
            text = self.small('SHA256SUMS').decode('ascii')
            sums = {}
            for line in text.splitlines():
                match = re.fullmatch(r'([0-9a-f]{64})  \./([^\s]+)', line)
                require(match is not None and match[2] not in sums)
                sums[match[2]] = match[1]
            require(sums == FILE_SHA, 'omarchy-bundle-checksums')
            fields = {}
            for line in self.small('BUNDLE-MANIFEST').decode('ascii').splitlines():
                key, value = line.split('=', 1)
                require(key not in fields)
                fields[key] = value
            require(fields == MANIFEST_FIELDS, 'omarchy-bundle-manifest')
            self.packages = {}
            for line in self.small('manifest/packages-aarch64-0.1.1.lock').decode('ascii').splitlines():
                name, version = line.split(' ', 1)
                require(re.fullmatch(r'[a-z0-9@._+-]+', name) and re.fullmatch(r'[A-Za-z0-9:._+~-]+', version))
                require(name not in self.packages)
                self.packages[name] = version
            require(all(self.packages.get(k) == v for k, v in REQUIRED_PACKAGES.items()), 'omarchy-package-closure')
            self.unchanged()
        except BaseException:
            self.close()
            raise

    def small(self, name):
        require(self.rows[name].size <= 1024 * 1024)
        with self.archive.extractfile(self.rows[name]) as data:
            return data.read(1024 * 1024 + 1)

    def unchanged(self):
        require(fingerprint(os.fstat(self.file.fileno())) == self.original, 'omarchy-bundle-changed')

    def copy(self, source, parent_fd, name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=parent_fd)
        with os.fdopen(fd, 'wb') as out, self.archive.extractfile(self.rows[source]) as data:
            value = hashlib.sha256()
            while True:
                block = data.read(1024 * 1024)
                if not block:
                    break
                out.write(block)
                value.update(block)
            out.flush()
            os.fsync(out.fileno())
            expected = FILE_SHA.get(source)
            require(expected is None or value.hexdigest() == expected, 'omarchy-copy-sha')
        self.unchanged()

    def close(self):
        if self.archive is not None:
            self.archive.close()
        self.file.close()


def read_journal(fd):
    with regular('install.json', 32768, fd) as data:
        return json.loads(data.read().decode('ascii'))


def save(fd, row):
    name = '.install-' + uuid.uuid4().hex
    out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=fd)
    with os.fdopen(out, 'wb') as stream:
        stream.write(json.dumps(row, sort_keys=True, separators=(',', ':')).encode('ascii'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(name, 'install.json', src_dir_fd=fd, dst_dir_fd=fd)
    os.fsync(fd)


def record_log(fd, row, owned):
    with regular('proot-install.log', 16 * 1024 * 1024, fd) as data:
        info = os.fstat(data.fileno())
        require(identity(info) == owned and stat.S_IMODE(info.st_mode) == 0o600, 'omarchy-log-replaced')
        row['install_log_size'] = info.st_size
        row['install_log_sha256'] = hashed(data)


def existing_container(prefix):
    for layout in ('containers', 'installed-rootfs'):
        parent = walk(prefix, 'var/lib/proot-distro/' + layout)
        if parent is not None:
            try:
                try:
                    os.stat(CONTAINER, dir_fd=parent, follow_symlinks=False)
                    return True
                except FileNotFoundError:
                    pass
            finally:
                os.close(parent)
    return False


def check_installed(root, prefix, row):
    for relative, field in (('var/lib/proot-distro/containers/' + CONTAINER, 'container_identity'),
                            ('var/lib/proot-distro/containers/' + CONTAINER + '/rootfs', 'rootfs_identity')):
        fd = walk(prefix, relative)
        require(fd is not None, 'omarchy-container-absent')
        try:
            require(identity(os.fstat(fd)) == row[field], 'omarchy-container-replaced')
        finally:
            os.close(fd)
    require(row['managed_files'] == {name: FILE_SHA[source] for name, source in HOST_FILES.items()})
    for name, value in row['managed_files'].items():
        parent = walk(root, str(PurePosixPath(name).parent))
        require(parent is not None)
        try:
            with regular(PurePosixPath(name).name, OUTER_BYTES, parent) as data:
                require(hashed(data) == value, 'omarchy-managed-file-changed')
        finally:
            os.close(parent)
    return dict(row, browser_linux_sandbox_disabled_in_bundle=True, browser_launched=False)


def install(archive, home, prefix, *, sources=None):
    # Canonicalize the Android /data/data alias once; managed children never follow symlinks.
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    runtime_sources = RuntimeSources(sources if sources is not None else Path(__file__).parent)
    source = Bundle(archive)
    root, root_fd, lock = home / '.local/share/loopy-omarchy', None, None
    try:
        prior = walk(home, '.local/share/loopy-omarchy')
        if prior is None:
            require(not existing_container(prefix), 'omarchy-container-exists')
            root_fd = walk(home, '.local/share/loopy-omarchy', True)
            row = {'schema': 1, 'uid': os.getuid(), 'root': identity(os.fstat(root_fd)),
                   'home': str(home), 'prefix': str(prefix), 'container': CONTAINER,
                   'bundle_sha256': OUTER_SHA, 'phase': 'NEW'}
            save(root_fd, row)
        else:
            root_fd = prior
            require(stat.S_IMODE(os.fstat(root_fd).st_mode) == 0o700, 'omarchy-managed-root-mode')
            try:
                row = read_journal(root_fd)
            except (OSError, ValueError):
                raise ValueError('omarchy-managed-root-unowned') from None
        lock = os.open('install.lock', os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600, dir_fd=root_fd)
        lock_info = os.fstat(lock)
        require(stat.S_ISREG(lock_info.st_mode) and lock_info.st_uid == os.getuid()
                and lock_info.st_nlink == 1 and stat.S_IMODE(lock_info.st_mode) == 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(row['schema'] == 1 and row['uid'] == os.getuid() and row['root'] == identity(os.fstat(root_fd)))
        require(row['home'] == str(home) and row['prefix'] == str(prefix)
                and row['container'] == CONTAINER and row['bundle_sha256'] == OUTER_SHA)
        if row['phase'] == 'INSTALLED':
            check_installed(root, prefix, row)
            native = runtime_sources.install(root_fd)
            if row.get('runtime_files') != native:
                row['runtime_files'] = native
                save(root_fd, row)
            return check_installed(root, prefix, row)
        require(row['phase'] in ('NEW', 'STAGED'), 'omarchy-install-uncertain')
        require(not existing_container(prefix), 'omarchy-container-exists')
        tool = prefix / 'bin/proot-distro'
        query = prefix / 'bin/dpkg-query'
        for program in (tool, query):
            with regular(program, 16 * 1024 * 1024) as executable:
                require(os.fstat(executable.fileno()).st_mode & 0o100)
        env = {'HOME': str(home), 'PREFIX': str(prefix), 'TERMUX__PREFIX': str(prefix),
               'TERMUX__HOME': str(home), 'TERMUX_APP__PACKAGE_NAME': 'com.termux',
               'ANDROID_ROOT': '/system', 'ANDROID_DATA': '/data',
               'PATH': str(prefix / 'bin') + ':/system/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(prefix / 'tmp')}
        version = subprocess.run([str(query), '-W', '-f=${Version}', 'proot-distro'], shell=False, env=env, stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=10, check=False)
        require(version.returncode == 0 and len(version.stdout) <= 128
                and supported_proot_version(version.stdout.strip()), 'omarchy-proot-version')
        if row['phase'] == 'NEW':
            row['phase'] = 'STAGING'
            save(root_fd, row)
            stage = walk(root, 'bundle', True)
            try:
                for name in source.rows:
                    parent = walk(root / 'bundle', str(PurePosixPath(name).parent), True)
                    try:
                        source.copy(name, parent, PurePosixPath(name).name)
                    finally:
                        os.close(parent)
            finally:
                os.close(stage)
            row['phase'] = 'STAGED'
            save(root_fd, row)
        for name, expected in FILE_SHA.items():
            parent = walk(root / 'bundle', str(PurePosixPath(name).parent))
            require(parent is not None)
            try:
                with regular(PurePosixPath(name).name, OUTER_BYTES, parent) as data:
                    require(hashed(data) == expected, 'omarchy-stage-changed')
            finally:
                os.close(parent)
        row['phase'] = 'INSTALLING'
        save(root_fd, row)
        log_owned = None
        row['install_exit_code'] = None
        try:
            log = os.open('proot-install.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=root_fd)
            log_owned = identity(os.fstat(log))
            with os.fdopen(log, 'wb') as output:
                try:
                    result = subprocess.run([str(tool), 'install', '--name', CONTAINER, '--architecture', 'aarch64',
                                             str(root / 'bundle/rootfs.tar.xz')], shell=False, env=env,
                                            stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                            timeout=1800, check=False)
                    row['install_exit_code'] = result.returncode
                finally:
                    output.flush()
                    os.fsync(output.fileno())
            record_log(root_fd, row, log_owned)
            require(result.returncode == 0, 'omarchy-proot-install')
            for relative, key in (('var/lib/proot-distro/containers/' + CONTAINER, 'container_identity'),
                                  ('var/lib/proot-distro/containers/' + CONTAINER + '/rootfs', 'rootfs_identity')):
                fd = walk(prefix, relative)
                require(fd is not None)
                try:
                    row[key] = identity(os.fstat(fd))
                finally:
                    os.close(fd)
            for name, original in HOST_FILES.items():
                fd = walk(root, str(PurePosixPath(name).parent), True)
                try:
                    source.copy(original, fd, PurePosixPath(name).name)
                finally:
                    os.close(fd)
            row['managed_files'] = {name: FILE_SHA[original] for name, original in HOST_FILES.items()}
            row['runtime_files'] = runtime_sources.install(root_fd)
            row['phase'] = 'INSTALLED'
            row['browser_linux_sandbox_disabled_in_bundle'], row['browser_launched'] = True, False
            save(root_fd, row)
            return check_installed(root, prefix, row)
        except BaseException:
            row['phase'] = 'INSTALL_UNKNOWN'
            if log_owned is not None:
                record_log(root_fd, row, log_owned)
            save(root_fd, row)
            raise ValueError('omarchy-install-uncertain') from None
    except OSError:
        raise ValueError('omarchy-install-filesystem') from None
    finally:
        if lock is not None:
            os.close(lock)
        if root_fd is not None:
            os.close(root_fd)
        source.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install the pinned separate loopy-omarchy container')
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--sources', type=Path, help='Directory of the pinned native runtime files')
    args = parser.parse_args(argv)
    result = install(args.bundle, os.environ['HOME'], os.environ['PREFIX'], sources=args.sources)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
