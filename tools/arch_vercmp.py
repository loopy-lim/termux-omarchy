"""Use the pinned original libalpm version comparator on the build host."""
import ctypes
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE_SHA = 'fa769e3081d25d74132109ca35a1e272a44b1c5674c397f3f2a1acaf3b6ab833'


class Comparator:
    def __init__(self, root, compiler='clang'):
        source = Path(root) / 'third_party/pacman-vercmp/version.c'
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA:
            raise ValueError('Original libalpm comparator source differs')
        self.temporary = tempfile.TemporaryDirectory(prefix='loopy-vercmp-')
        directory = Path(self.temporary.name)
        (directory / 'util.h').write_text('#include <stdlib.h>\n#define SYMEXPORT\n')
        library = directory / ('vercmp.dylib' if sys.platform == 'darwin' else 'vercmp.so')
        subprocess.run([compiler, '-shared', '-fPIC', '-O2', '-I', str(directory), str(source), '-o', str(library)],
                       check=True, capture_output=True, timeout=30)
        self.library = ctypes.CDLL(str(library))
        self.function = self.library.alpm_pkg_vercmp
        self.function.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.function.restype = ctypes.c_int

    def __call__(self, actual, required):
        return self.function(actual.encode('ascii'), required.encode('ascii'))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.temporary.cleanup()
