"""Browser addresses and persistent profile paths, independent of GTK."""
import os
from pathlib import Path
from urllib.parse import quote_plus, urlsplit


def address(value):
    value = value.strip()
    if not value or value == "about:blank":
        return "about:blank"
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("주소에 제어 문자를 넣을 수 없습니다.")
    if value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        if not parsed.hostname or parsed.port == 0:
            raise ValueError("웹 주소를 확인하세요.")
        return value
    if "://" in value or value.lower().startswith(("javascript:", "data:", "file:")):
        raise ValueError("http 또는 https 주소를 입력하세요.")
    if " " in value or not ("." in value or value.startswith("localhost") or ":" in value):
        return "https://duckduckgo.com/?q=" + quote_plus(value)
    return address("http://" + value if value.startswith(("localhost", "127.", "[::1]"))
                   else "https://" + value)


def profile_paths(environment=None):
    environment = os.environ if environment is None else environment
    home = Path(environment.get("HOME", "/root"))
    def directory(key, fallback):
        value = Path(environment.get(key, str(home / fallback)))
        return value if value.is_absolute() else home / fallback
    return (directory("XDG_DATA_HOME", ".local/share") / "loopy-browser",
            directory("XDG_CACHE_HOME", ".cache") / "loopy-browser")
