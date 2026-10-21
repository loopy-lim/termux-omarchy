#!/usr/bin/env python3
"""Build pinned Android PRoot with guarded signal and identity compatibility patches."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import shlex
from android_elf import verify_android_elf


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/proot-compat"
LOCALDESKTOP = BUILD / "localdesktop"
LOCALDESKTOP_COMMIT = "e6a8b580a3376e842cca2e44327a99498d7fb6dc"
PROOT_COMMIT = "ab2e3464d04483b98a0614b470f3f8950d5a6468"
PROOT_SUBTREE = "patches/build-proot-android/build/proot"
TALLOC_SUBTREE = "patches/build-proot-android/build/talloc-2.4.3"
PROOT_TREE = "904c9e8f0081ef4c0796676ceded40c500958f5b"
TALLOC_TREE = "cbf8656981807ff2979113c19f20dbdfbfee9e62"
EVENT_SHA256 = "5b6c52b10124c2652f92951b0fbbf98b7067dbfe3034a7079918ac329486653b"
PATCH_NAMES = ("0001-forward-tagged-sigsys.patch", "0002-preserve-same-kernel-identity.patch")


def patches():
    return tuple(ROOT / "native/proot-compat" / name for name in PATCH_NAMES)
LOCK = ROOT / "third_party/runtime.lock.json"
NDK_VERSION = "27.1.12297006"
API = 21  # The pinned LocalDesktop PRoot build uses API 21.
LINK_FLAGS = ("-Wl,-z,max-page-size=16384", "-Wl,-z,common-page-size=16384")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    return {str(path.relative_to(ROOT)): digest(path)
            for path in (*patches(), ROOT / "tools/build_proot_compat.py", LOCK,
                         ROOT / "tools/android_elf.py")}


def upstream_hashes(source, talloc):
    return {str(path.relative_to(ROOT)): digest(path)
            for tree in (source, talloc) for path in sorted(tree.rglob("*")) if path.is_file()}


def run(args, *, cwd=None, env=None, log=None):
    if log is None:
        result = subprocess.run(args, cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"{args[0]} failed:\n{result.stdout[-4000:]}")
        return result.stdout.strip()
    with log.open("a") as stream:
        result = subprocess.run(args, cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed; see {log}")
    return ""


def toolchain():
    sdk = Path(os.environ.get("ANDROID_SDK_ROOT", Path.home() / "Library/Android/sdk"))
    configured = Path(os.environ.get("ANDROID_NDK_HOME", sdk / "ndk" / NDK_VERSION))
    ndk = configured if configured.name == NDK_VERSION else configured / "ndk" / NDK_VERSION
    host = "darwin-x86_64" if sys.platform == "darwin" else "linux-x86_64"
    base = ndk / "toolchains/llvm/prebuilt" / host / "bin"
    names = (f"aarch64-linux-android{API}-clang", "llvm-ar", "llvm-strip",
             "llvm-objcopy", "llvm-objdump", "llvm-readelf")
    result = {name: base / name for name in names}
    missing = [str(path) for path in result.values() if not path.is_file()]
    if missing or ndk.name != NDK_VERSION:
        raise RuntimeError(f"NDK {NDK_VERSION} required; missing {missing}")
    return result


def checkout_pinned_source():
    BUILD.mkdir(parents=True, exist_ok=True)
    if not (LOCALDESKTOP / ".git").exists():
        run(["git", "clone", "--filter=blob:none", "--no-checkout",
             "https://github.com/localdesktop/localdesktop.github.io.git",
             str(LOCALDESKTOP)])
    run(["git", "-C", str(LOCALDESKTOP), "sparse-checkout", "set",
         PROOT_SUBTREE, TALLOC_SUBTREE])
    run(["git", "-C", str(LOCALDESKTOP), "checkout", "--detach",
         LOCALDESKTOP_COMMIT])
    head = run(["git", "-C", str(LOCALDESKTOP), "rev-parse", "HEAD"])
    if head != LOCALDESKTOP_COMMIT:
        raise RuntimeError("LocalDesktop source commit changed")
    for subtree, expected in ((PROOT_SUBTREE, PROOT_TREE),
                              (TALLOC_SUBTREE, TALLOC_TREE)):
        actual = run(["git", "-C", str(LOCALDESKTOP), "rev-parse",
                      f"HEAD:{subtree}"])
        if actual != expected:
            raise RuntimeError(f"Vendored source tree changed: {subtree}")
    dirty = run(["git", "-C", str(LOCALDESKTOP), "status", "--porcelain",
                 "--untracked-files=all", "--", PROOT_SUBTREE, TALLOC_SUBTREE])
    if dirty:
        raise RuntimeError("Vendored PRoot/talloc source has local changes")
    source = LOCALDESKTOP / PROOT_SUBTREE
    if digest(source / "src/tracee/event.c") != EVENT_SHA256:
        raise RuntimeError("Pinned PRoot event.c does not match reviewed source")
    return source, LOCALDESKTOP / TALLOC_SUBTREE


def build_talloc(talloc, tools, log):
    static = BUILD / "static"
    include = static / "include"
    lib = static / "lib"
    include.mkdir(parents=True, exist_ok=True)
    lib.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(talloc / "talloc.h", include / "talloc.h")
    object_file = static / "talloc.o"
    run([str(tools[f"aarch64-linux-android{API}-clang"]), "-O2", "-fPIC",
         f"-ffile-prefix-map={ROOT}=.",
         "-D__STDC_WANT_LIB_EXT1__=1", f"-I{talloc}",
         f"-I{talloc / 'lib/replace'}", f"-I{talloc / 'bin/default'}",
         "-c", str(talloc / "talloc.c"), "-o", str(object_file)], log=log)
    run([str(tools["llvm-ar"]), "rcs", str(lib / "libtalloc.a"),
         str(object_file)], log=log)
    return static


def loader_offset(loader, readelf):
    symbols = {}
    for line in run([str(readelf), "-s", str(loader)]).splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[-1] in {"_start", "pokedata_workaround"}:
            symbols[fields[-1]] = int(fields[1], 16)
    if set(symbols) != {"_start", "pokedata_workaround"}:
        raise RuntimeError("Cannot find ARM64 loader workaround symbols")
    offset = symbols["pokedata_workaround"] - symbols["_start"]
    if not 0 < offset < 65536:
        raise RuntimeError(f"Invalid loader workaround offset: {offset}")
    return offset


def check_elf(path, elf_type):
    data = path.read_bytes()[:20]
    if len(data) < 20 or data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise RuntimeError(f"Not a 64-bit little-endian ELF: {path}")
    if int.from_bytes(data[16:18], "little") != elf_type or int.from_bytes(data[18:20], "little") != 183:
        raise RuntimeError(f"Unexpected ELF type or architecture: {path}")


def main():
    if not all(patch.is_file() for patch in patches()) or not LOCK.is_file():
        raise RuntimeError("Pinned patch or runtime lock is missing")
    inputs = source_hashes()
    tools = toolchain()
    source, talloc = checkout_pinned_source()
    upstream = upstream_hashes(source, talloc)
    work = BUILD / "work"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(source, work)
    log = BUILD / "build.log"
    log.write_text("")
    for patch in patches():
        run(["patch", "-p1", "-F", "0", "-i", str(patch)], cwd=work, log=log)
    static = build_talloc(talloc, tools, log)
    compiler = tools[f"aarch64-linux-android{API}-clang"]
    env = os.environ.copy()
    env.update(CC=str(compiler), STRIP=str(tools["llvm-strip"]),
               OBJCOPY=str(tools["llvm-objcopy"]),
               OBJDUMP=str(tools["llvm-objdump"]),
               CFLAGS=(f"-I{static / 'include'} -Werror=implicit-function-declaration "
                       f"-ffile-prefix-map={ROOT}=."),
               LDFLAGS=f"-L{static / 'lib'}", PROOT_UNBUNDLE_LOADER=".")
    src = work / "src"
    # The pinned loader bypasses LDFLAGS and invokes LD with LOADER_LDFLAGS.
    # A command-line LD covers both links while preserving those loader options.
    linker = "LD=" + shlex.join([str(compiler), *LINK_FLAGS])
    # macOS awk lacks GNU strtonum and word-boundary escapes used by the
    # upstream loader-info.awk. Generate the same offset from llvm-readelf.
    run(["make", "-C", str(src), linker, "loader/loader"], env=env, log=log)
    offset = loader_offset(src / "loader/loader", tools["llvm-readelf"])
    (src / "loader/loader-info.c").write_text(
        f"#include <unistd.h>\nconst ssize_t offset_to_pokedata_workaround={offset};\n")
    run(["make", "-C", str(src), linker, "proot"], env=env, log=log)
    out = BUILD / "arm64-v8a"
    out.mkdir(parents=True, exist_ok=True)
    app = out / "libproot.so"
    loader = out / "libproot_loader.so"
    app_tmp = app.with_suffix(".so.tmp")
    loader_tmp = loader.with_suffix(".so.tmp")
    shutil.copyfile(src / "proot", app_tmp)
    shutil.copyfile(src / "loader/loader", loader_tmp)
    run([str(tools["llvm-strip"]), str(app_tmp), str(loader_tmp)], log=log)
    check_elf(app_tmp, 3)  # PIE executable
    check_elf(loader_tmp, 2)  # fixed-address static loader
    elf = verify_android_elf(app_tmp.read_bytes())
    loader_elf = verify_android_elf(loader_tmp.read_bytes())
    try:
        unchanged = source_hashes() == inputs and upstream_hashes(source, talloc) == upstream
    except OSError as error:
        raise RuntimeError("Source changed during PRoot build") from error
    if not unchanged:
        raise RuntimeError("Source changed during PRoot build")
    app_tmp.replace(app)
    loader_tmp.replace(loader)
    receipt = {
        "schema_version": 1,
        "inputs": inputs, "upstream_sources_sha256": upstream,
        "link_flags": list(LINK_FLAGS), "elf": elf, "loader_elf": loader_elf,
        "artifact": {"path": str(app.relative_to(ROOT)), "sha256": digest(app),
                     "bytes": app.stat().st_size},
        "loader_artifact": {"path": str(loader.relative_to(ROOT)),
                            "sha256": digest(loader), "bytes": loader.stat().st_size},
        "provenance": {
            "localdesktop_commit": LOCALDESKTOP_COMMIT,
            "vendored_proot_commit": PROOT_COMMIT,
            "proot_git_tree": PROOT_TREE,
            "talloc_git_tree": TALLOC_TREE,
            "pinned_event_source_sha256": EVENT_SHA256,
            "patched_event_sha256": digest(src / "tracee/event.c"),
            "patched_seccomp_sha256": digest(src / "tracee/seccomp.c"),
            "talloc_source_sha256": digest(talloc / "talloc.c"),
            "compiler": str(compiler), "compiler_sha256": digest(compiler),
            "ndk_version": NDK_VERSION, "android_api": API,
            "loader_workaround_offset": offset,
            "runtime_validation": "pending ordinary-UID Android VM",
        },
    }
    (BUILD / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Built experimental PRoot: {app} ({receipt['artifact']['sha256']})")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"PRoot compatibility build failed: {error}", file=sys.stderr)
        sys.exit(1)
