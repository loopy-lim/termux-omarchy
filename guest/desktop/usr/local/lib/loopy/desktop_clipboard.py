#!/usr/bin/python3
"""Session-scoped UTF-8 clipboard records for the inner Sway compositor."""

import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

LIMIT = 65536
MAX_OWNERS = 8


def read_record(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Clipboard record must not be a symlink")
    if not path.is_file():
        return None, None
    with path.open("rb") as source:
        metadata = os.fstat(source.fileno())
        data = source.read(LIMIT + 1)
    if len(data) > LIMIT or b"\0" in data:
        raise ValueError("Clipboard record exceeds the plain-text limit")
    revision = (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, metadata.st_size)
    return data.decode("utf-8"), revision


def read_text(path):
    return read_record(path)[0]


def publish(path, data):
    path = Path(path)
    if len(data) > LIMIT or b"\0" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Clipboard directory must not be a symlink")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".clipboard-", delete=False) as target:
        temporary = Path(target.name)
        try:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return True


def paths():
    token = os.environ["LOOPY_SESSION"]
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", token):
        raise ValueError("Invalid clipboard session token")
    directory = Path("/run/loopy")
    return directory / ("clip-android-" + token), directory / ("clip-guest-" + token)


def export():
    android, guest = paths()
    state = os.environ.get("CLIPBOARD_STATE", "data")
    if state in ("nil", "clear"):
        if state == "nil" and not guest.exists():
            return
        data = b""
    elif state == "sensitive":
        return
    else:
        data = sys.stdin.buffer.read(LIMIT + 1)
    publish(guest, data)


def watch():
    android, _ = paths()
    exporter = subprocess.Popen(["wl-paste", "--type", "text", "--watch", "python3", __file__, "export"])
    notifications = subprocess.Popen(["/bin/busybox", "inotifyd", "-", str(android.parent) + ":yw"], stdout=subprocess.PIPE, text=True)
    owners, previous_revision = [], None

    def reap_owners():
        alive = []
        for process in owners:
            if process.poll() is None:
                alive.append(process)
            else:
                process.wait(timeout=0)
        owners[:] = alive

    def import_android():
        nonlocal previous_revision
        text, revision = read_record(android)
        if text is None or revision == previous_revision:
            return
        reap_owners()
        if text == "":
            subprocess.run(["wl-copy", "--clear"], check=True, timeout=5)
        else:
            if len(owners) >= MAX_OWNERS:
                raise ValueError("Clipboard selection owner limit reached")
            owner = subprocess.Popen(["wl-copy", "--foreground", "--type", "text/plain;charset=utf-8"], stdin=subprocess.PIPE)
            try:
                owner.stdin.write(text.encode())
                owner.stdin.close()
            except (OSError, ValueError):
                owner.terminate()
                owner.wait(timeout=3)
                raise
            owners.append(owner)
        previous_revision = revision

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        import_android()
        for event in notifications.stdout:
            fields = event.rstrip("\n").split("\t")
            if len(fields) == 3 and "y" in fields[0] and fields[2] == android.name:
                try:
                    import_android()
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    print(f"Desktop clipboard import failed: {error}", file=sys.stderr)
    finally:
        for process in (*owners, exporter, notifications):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if notifications.stdout:
            notifications.stdout.close()


if __name__ == "__main__":
    try:
        export() if len(sys.argv) > 1 and sys.argv[1] == "export" else watch()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Desktop clipboard failed: {error}", file=sys.stderr)
        sys.exit(1)
