#!/usr/bin/python3
"""Register the real Android app UID for D-Bus without fake-root privileges."""

import os
from pathlib import Path
import stat
import sys
import tempfile


LIMIT = 65536
NAME = "loopy"


def read_database(path):
    path = Path(path)
    if any(parent.is_symlink() for parent in path.parents) or path.is_symlink():
        raise ValueError("Identity database crosses a symlink")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT \
                or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError("Identity database is not a bounded app-owned file")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            content = source.read(LIMIT + 1)
        if len(content) > LIMIT or b"\0" in content:
            raise ValueError("Identity database is invalid or oversized")
        text = content.decode("utf-8")
        if text and not text.endswith("\n"):
            raise ValueError("Identity database lacks a final newline")
        return text, stat.S_IMODE(info.st_mode)
    finally:
        os.close(descriptor)


def rows(text, count):
    records = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split(":")
        if len(fields) != count or not fields[2].isdigit():
            raise ValueError("Identity database contains an invalid record")
        records.append(fields)
    return records


def atomic_append(path, original, line, mode):
    value = (original + line).encode("utf-8")
    if len(value) > LIMIT:
        raise ValueError("Identity database would exceed its limit")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".loopy-identity-", delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(value)
            output.flush()
            os.fchmod(output.fileno(), mode)
            os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def ensure_identity(directory=Path("/etc"), uid=None, gid=None):
    uid = os.getuid() if uid is None else uid
    gid = os.getgid() if gid is None else gid
    if type(uid) is not int or type(gid) is not int or not 0 < uid < 2**31 or not 0 < gid < 2**31:
        raise ValueError("Desktop requires an ordinary app UID and GID")
    directory = Path(directory)
    passwd_path, group_path = directory / "passwd", directory / "group"
    passwd, passwd_mode = read_database(passwd_path)
    group, group_mode = read_database(group_path)
    users, groups = rows(passwd, 7), rows(group, 4)
    if not any(row[0] == "root" and row[2] == "0" for row in users) \
            or not any(row[0] == "root" and row[2] == "0" for row in groups):
        raise ValueError("Identity database lacks root")
    if any(row[0] == NAME and row[2] != str(uid) for row in users) \
            or any(row[0] == NAME and row[2] != str(gid) for row in groups):
        raise ValueError("Desktop identity name is already assigned")
    add_user = not any(row[2] == str(uid) for row in users)
    add_group = not any(row[2] == str(gid) for row in groups)
    if add_user:
        atomic_append(passwd_path, passwd, f"{NAME}:x:{uid}:{gid}:Loopy Desktop:/root:/bin/bash\n", passwd_mode)
    if add_group:
        atomic_append(group_path, group, f"{NAME}:x:{gid}:\n", group_mode)


if __name__ == "__main__":
    try:
        ensure_identity()
    except (OSError, UnicodeError, ValueError):
        print("Desktop UID initialization failed", file=sys.stderr)
        sys.exit(1)
