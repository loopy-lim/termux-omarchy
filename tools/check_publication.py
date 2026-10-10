#!/usr/bin/env python3
"""Read-only source and distribution metadata checks; never touches Android."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".git", "__pycache__", ".venv", "build", "cache", "dist", "local"}
BLOCKED_SUFFIXES = {
    ".apk", ".aab", ".dex", ".class", ".so", ".deb", ".jks", ".keystore",
    ".p12", ".pem", ".key", ".zip", ".tar", ".gz", ".xz", ".png", ".jpg",
    ".jpeg", ".webp", ".mp4", ".sqlite", ".db",
}
PRIVATE_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "cloud-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "host-home": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "device-serial": re.compile(r"\bHA[0-9A-Z]{6,}\b"),
    "tailnet-address": re.compile(r"\b100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.\d{1,3}\.\d{1,3}\b"),
}
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")


def source_files():
    found = set()
    for base, dirs, names in os.walk(ROOT, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED)
        for directory in dirs:
            path = Path(base) / directory
            if path.is_symlink():
                raise ValueError(f"symlink directory: {path.relative_to(ROOT)}")
        for name in sorted(names):
            path = Path(base) / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"non-regular source: {path.relative_to(ROOT)}")
            found.add(path)
            yield path
    # A tracked file must not escape checks by being placed in an ignored folder.
    if (ROOT / ".git").exists():
        result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                                capture_output=True, check=True, timeout=10)
        for name in result.stdout.decode().split("\0"):
            if not name:
                continue
            path = ROOT / name
            if path in found:
                continue
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
                raise ValueError(f"non-regular tracked source: {name}")
            yield path


def inspect_sources():
    files, texts, problems = list(source_files()), {}, []
    for path in files:
        relative = str(path.relative_to(ROOT))
        if path.suffix.lower() in BLOCKED_SUFFIXES or path.name.startswith(".env"):
            problems.append(f"excluded distribution file: {relative}")
            continue
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024 or b"\0" in data:
            problems.append(f"non-source or oversized file: {relative}")
            continue
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"non-UTF8 source: {relative}")
            continue
        texts[path] = content
        for label, pattern in PRIVATE_PATTERNS.items():
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                problems.append(f"{label}: {relative}:{line}")
        python_script = content.startswith("#!") and "python" in content.split("\n", 1)[0]
        if path.suffix == ".py" or python_script:
            try:
                compile(content, relative, "exec")
            except SyntaxError as error:
                problems.append(f"Python syntax: {relative}:{error.lineno}")
        if path.suffix == ".json":
            try:
                json.loads(content)
            except ValueError:
                problems.append(f"JSON syntax: {relative}")
        if path.suffix == ".toml":
            try:
                tomllib.loads(content)
            except ValueError:
                problems.append(f"TOML syntax: {relative}")
    for path, content in texts.items():
        if path.suffix != ".md":
            continue
        for match in LINK.finditer(content):
            target = match.group(1).strip().split(" \"", 1)[0].strip("<>")
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            resolved = (path.parent / unquote(parts.path)).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                problems.append(f"broken/local external link: {path.relative_to(ROOT)} -> {target}")
    for name in ("LICENSE", "NOTICE.md", "README.md", "README.ko.md", "legal/README.md",
                 "docs/INSTALL.md", "docs/INSTALL.ko.md", "docs/DEVELOPMENT.md",
                 "docs/DEVELOPMENT.ko.md", "docs/VALIDATION.md", "input/README.md"):
        if not (ROOT / name).is_file():
            problems.append(f"required source document missing: {name}")
    if problems:
        raise ValueError("\n".join(problems))
    print(f"publication source boundaries: PASS ({len(files)} text files)", flush=True)
    return texts


def verify_notices():
    catalog = json.loads((ROOT / "legal/license-sources.json").read_text())
    rows = catalog["licenses"]
    for row in rows:
        path = (ROOT / "legal" / row["path"]).resolve()
        if not path.is_relative_to(ROOT / "legal/licenses"):
            raise ValueError("license inventory path is outside legal/licenses")
        data = path.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"retained license changed: {row['path']}")
    if (ROOT / "LICENSE").read_bytes() != (ROOT / "legal/licenses/termux-x11-GPL-3.0.txt").read_bytes():
        raise ValueError("root GPL license differs from retained upstream text")
    print(f"retained license texts: PASS ({len(rows)} copies)", flush=True)


def execute(command):
    print("check: " + " ".join(command), flush=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=240)


def shell_syntax(texts):
    zsh = shutil.which("zsh")
    if not zsh:
        raise ValueError("zsh is required for profile syntax checks")
    for path, content in texts.items():
        if path.suffix == ".zsh" or path.name == "zshrc":
            execute([zsh, "-n", str(path.relative_to(ROOT))])
        elif content.startswith("#!/bin/sh\n"):
            execute(["/bin/sh", "-n", str(path.relative_to(ROOT))])
        elif content.startswith("#!/bin/bash\n"):
            execute(["bash", "-n", str(path.relative_to(ROOT))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-only", action="store_true", help="check text boundaries/links/syntax only")
    args = parser.parse_args()
    try:
        texts = inspect_sources()
        verify_notices()
        if not args.metadata_only:
            shell_syntax(texts)
            execute([sys.executable, "-B", "installer/verify.py"])
            execute([sys.executable, "-B", "input/build.py", "--check"])
            execute([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/runtime", "-v"])
            execute([sys.executable, "-B", "tests/input/run_host.py"])
            execute([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/publication", "-v"])
        print("publication checks: PASS", flush=True)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
