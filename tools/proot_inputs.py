"""Select a patched PRoot only with intact, recorded build inputs."""
import hashlib
import json
from pathlib import Path


class CompatError(Exception):
    """The derived runtime cannot be attributed to current sources."""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_file(root, name):
    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise CompatError("Invalid PRoot build receipt path")
    path = root / name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise CompatError(f"Missing or unsafe PRoot build input: {name}")
    return path


def select_proot(root, original):
    root = root.resolve()
    patches = sorted((root / "native/proot-compat").glob("*.patch"))
    if not patches:
        return original, []
    receipt_path = local_file(root, "build/proot-compat/build-receipt.json")
    try:
        receipt = json.loads(receipt_path.read_text())
        if receipt["schema_version"] != 1 or not isinstance(receipt["inputs"], dict):
            raise CompatError("Unsupported PRoot build receipt")
        required = {str(path.relative_to(root)) for path in patches}
        required.update(("tools/build_proot_compat.py", "third_party/runtime.lock.json"))
        if not required.issubset(receipt["inputs"]):
            raise CompatError("PRoot receipt omits current patches or builder inputs")
        inputs = [receipt_path]
        for name, expected in receipt["inputs"].items():
            path = local_file(root, name)
            if digest(path) != expected:
                raise CompatError(f"PRoot build input changed: {name}; rebuild runtime")
            inputs.append(path)
        artifact = receipt["artifact"]
        if artifact["path"] != "build/proot-compat/arm64-v8a/libproot.so":
            raise CompatError("Unexpected derived PRoot artifact path")
        binary = local_file(root, artifact["path"])
        if digest(binary) != artifact["sha256"] or binary.stat().st_size != artifact["bytes"]:
            raise CompatError("Derived PRoot binary changed; rebuild runtime")
        loader_record = receipt["loader_artifact"]
        if loader_record["path"] != "build/proot-compat/arm64-v8a/libproot_loader.so":
            raise CompatError("Unexpected derived PRoot loader path")
        loader = local_file(root, loader_record["path"])
        if digest(loader) != loader_record["sha256"] or loader.stat().st_size != loader_record["bytes"]:
            raise CompatError("Derived PRoot loader changed; rebuild runtime")
        inputs.append(loader)
        return binary, inputs
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CompatError(f"Invalid PRoot build receipt: {exc}") from exc
