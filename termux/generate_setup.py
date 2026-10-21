"""Generate one self-contained setup script for pasting into native Termux."""
import base64
import hashlib
import io
from pathlib import Path
import zipfile

FILES = ('runtime.py', 'processes.py', 'preferences.py', 'install.py', 'i3.config')


def generate(source):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (Path(source) / name).read_bytes())
    payload = data.getvalue()
    encoded = base64.b64encode(payload).decode()
    digest = hashlib.sha256(payload).hexdigest()
    return '''#!/data/data/com.termux/files/usr/bin/bash
set -eu
if [ "${PREFIX:-}" != /data/data/com.termux/files/usr ] || [ "${HOME:-}" != /data/data/com.termux/files/home ]; then
    echo "Run this installer in the primary-user native Termux shell." >&2
    exit 1
fi
pkg install -y x11-repo
pkg install -y python termux-x11-nightly i3 xfce4-terminal mousepad pcmanfm dmenu dbus xorg-xdpyinfo xorg-xprop
python3 - <<'LOOPY_NATIVE_SETUP_PY'
import base64, hashlib, io, os, sys, tempfile, zipfile
from pathlib import Path
payload = base64.b64decode(''' + repr(encoded) + ''', validate=True)
if hashlib.sha256(payload).hexdigest() != ''' + repr(digest) + ''':
    raise SystemExit('native installer payload hash mismatch')
with tempfile.TemporaryDirectory(prefix='loopy-native-') as temporary:
    source = Path(temporary)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if set(archive.namelist()) != set(''' + repr(FILES) + ''') or any(i.file_size > 65536 for i in archive.infolist()):
            raise SystemExit('invalid native installer payload')
        for name in archive.namelist():
            (source / name).write_bytes(archive.read(name))
    sys.path.insert(0, str(source))
    from install import install
    root = install(Path.home(), source)
print('Native i3/X11 setup complete: ' + str(root))
print('Termux RUN_COMMAND permission and allow-external-apps remain your explicit choice.')
LOOPY_NATIVE_SETUP_PY
'''


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    output = root / 'android/assets/loopy-termux-setup.sh'
    output.write_text(generate(root / 'termux'))
    print(output)
