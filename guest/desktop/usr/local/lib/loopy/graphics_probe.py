#!/usr/bin/env python3
"""Bounded app-UID guest evidence. No offscreen result enables desktop hardware."""
import argparse
import glob
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

SCHEMA = 1
OUTPUT_LIMIT = 16384
CHILD_TIMEOUT = 5.0
GL_PROVIDERS = ("mesa-default", "llvmpipe", "softpipe", "virpipe")
CONTEXT = "guest UID; offscreen EGL/GLES2 only; desktop presentation unsupported"
SOCKET = re.compile(r"/run/loopy/virgl-[A-Za-z0-9-]{1,64}\.sock\Z")


def unavailable(provider, reason, renderer="", pixels=False, status="failed"):
    return {"id": provider, "status": status, "reason": str(reason)[:512],
            "renderer": renderer[:512], "pixelVerified": pixels is True,
            "presentationVerified": False}


def validate_attempt(provider, attempt):
    """Renderer evidence and actual pixels are required; child labels are untrusted."""
    if not isinstance(attempt, dict) or attempt.get("id") != provider:
        return unavailable(provider, "invalid provider result")
    renderer = attempt.get("renderer", "")
    if not isinstance(renderer, str) or len(renderer) > 512:
        return unavailable(provider, "invalid renderer result")
    pixels = attempt.get("pixelVerified") is True
    if not pixels:
        return unavailable(provider, attempt.get("reason", "offscreen pixels not verified"), renderer)
    if provider == "mesa-default":
        software = any(name in renderer.lower() for name in
                       ("llvmpipe", "softpipe", "swrast", "lavapipe", "swiftshader", "virpipe", "virgl"))
        reason = ("default EGL resolved to software/proxy; hardware not established" if software
                  else "offscreen pixels verified; desktop presentation unsupported")
        return unavailable(provider, reason, renderer, True, "blocked")
    if provider == "virpipe":
        if not renderer.lower().startswith("virgl"):
            return unavailable(provider, "renderer does not match VirGL proxy", renderer)
        return unavailable(provider, "VirGL proxy offscreen pixels verified; backend hardware and presentation unverified",
                           renderer, True, "ready")
    if provider not in ("llvmpipe", "softpipe") or not renderer.lower().startswith(provider):
        return unavailable(provider, "renderer does not match requested software provider", renderer)
    return unavailable(provider, "software offscreen pixels verified; desktop presentation not tested",
                       renderer, True, "ready")


def select_provider(providers):
    for provider in ("llvmpipe", "softpipe"):
        for attempt in providers:
            if attempt.get("id") == provider and validate_attempt(provider, attempt)["status"] == "ready":
                return provider
    return "cairo"


def validate_socket(path):
    if not isinstance(path, str) or not SOCKET.fullmatch(path):
        raise ValueError("VirGL socket must be /run/loopy/virgl-TOKEN.sock")
    return path


def socket_available(path):
    if not path:
        return False
    validate_socket(path)
    try:
        # A socket inode is only a prerequisite; the EGL child must really connect/render.
        return stat.S_ISSOCK(os.lstat(path).st_mode)
    except OSError:
        return False


def provider_environment(provider, virgl_socket=None):
    if provider not in GL_PROVIDERS:
        raise ValueError("unknown graphics provider")
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/root",
                   "TMPDIR": "/tmp", "EGL_PLATFORM": "surfaceless",
                   "MESA_SHADER_CACHE_DISABLE": "true"}
    if provider in ("llvmpipe", "softpipe"):
        environment.update(LIBGL_ALWAYS_SOFTWARE="true", GALLIUM_DRIVER=provider)
    elif provider == "virpipe":
        environment.update(LIBGL_ALWAYS_SOFTWARE="true", GALLIUM_DRIVER="virpipe",
                           VTEST_SOCKET_NAME=validate_socket(virgl_socket))
    return environment


def run_bounded(command, environment, timeout=CHILD_TIMEOUT):
    """Drain two pipes with strict byte/deadline limits, then reap the owned child."""
    output = {"stdout": "", "error": "", "returncode": -1}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    process = None
    try:
        process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    output["error"] = "probe timeout"
                    break
                for key, _ in selector.select(min(remaining, .1)):
                    data = os.read(key.fd, 4096)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = buffers[key.data]
                    limit = OUTPUT_LIMIT if key.data == "stdout" else 4096
                    extent = len(buffer) + len(data)
                    buffer.extend(data[:max(0, limit - len(buffer))])
                    if extent >= limit:
                        output["error"] = "probe output limit exceeded"
                        break
                if output["error"]:
                    break
            if not output["error"]:
                remaining = deadline - time.monotonic()
                try:
                    process.wait(timeout=max(0, remaining))
                except subprocess.TimeoutExpired:
                    output["error"] = "probe timeout"
    except (OSError, ValueError) as error:
        output["error"] = "probe child failed: " + str(error)[:256]
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=1)
            output["returncode"] = process.returncode
            process.stdout.close()
            process.stderr.close()
    output["stdout"] = buffers["stdout"].decode("utf-8", errors="replace")
    if not output["error"] and output["returncode"] != 0:
        detail = buffers["stderr"].decode("utf-8", errors="replace")[:256]
        output["error"] = f"probe child exit {output['returncode']}: {detail}"
    return output


def decode_attempt(provider, document):
    if len(document.encode("utf-8")) > OUTPUT_LIMIT:
        return unavailable(provider, "probe JSON output limit exceeded")
    try:
        report = json.loads(document)
        if not isinstance(report, dict) or type(report.get("schema")) is not int or report["schema"] != SCHEMA:
            raise ValueError("invalid schema")
        if type(report.get("uid")) is not int or report["uid"] != os.getuid():
            raise ValueError("probe UID differs from parent")
        attempts = report.get("providers")
        if not isinstance(attempts, list) or len(attempts) != 1:
            raise ValueError("invalid provider list")
        return validate_attempt(provider, attempts[0])
    except (ValueError, TypeError, KeyError):
        return unavailable(provider, "malformed or mismatched probe JSON")


def probe_provider(provider, virgl_socket=None):
    command = [sys.executable, str(Path(__file__).resolve()), "--provider", provider]
    if provider == "virpipe":
        command.extend(["--virgl-socket", validate_socket(virgl_socket)])
    child = run_bounded(command, provider_environment(provider, virgl_socket))
    if child["error"]:
        return unavailable(provider, child["error"])
    return decode_attempt(provider, child["stdout"])


def device_inventory(paths=None):
    if paths is None:
        paths = ["/dev/kgsl-3d0"] + sorted(glob.glob("/dev/dri/renderD*"))[:15]
    devices = []
    for path in paths[:16]:
        try:
            fd = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NONBLOCK)
            os.close(fd)
            devices.append({"path": path, "opened": True, "errno": 0})
        except OSError as error:
            devices.append({"path": path, "opened": False, "errno": error.errno})
    return devices


def catalog():
    return [
        unavailable("mesa-default", "desktop GPU presentation unsupported (host accepts wl_shm)", status="blocked"),
        unavailable("llvmpipe", "offscreen probe not run", status="blocked"),
        unavailable("softpipe", "offscreen probe not run", status="blocked"),
        unavailable("cairo", "existing pixman/cairo desktop path; does not provide OpenGL", status="ready"),
        unavailable("virpipe", "VirGL socket not provided; context/pixels/backend unverified", status="blocked"),
        unavailable("turnip", "Vulkan ICD/device render/presentation not verified", status="blocked"),
        unavailable("zink", "Vulkan provider and GL presentation not verified", status="blocked"),
    ]


def build_report(inventory=False, prober=probe_provider, devices=None, virgl_socket=None):
    providers = catalog()
    if virgl_socket:
        validate_socket(virgl_socket)
        if not inventory and socket_available(virgl_socket):
            providers[4] = validate_attempt("virpipe", prober("virpipe", virgl_socket))
        else:
            providers[4] = unavailable("virpipe", "VirGL socket unavailable or context probe not run", status="blocked")
    if not inventory:
        for provider in ("llvmpipe", "softpipe"):
            attempt = validate_attempt(provider, prober(provider))
            providers[GL_PROVIDERS.index(provider)] = attempt
            if attempt["status"] == "ready":
                break
    return {"schema": SCHEMA, "uid": os.getuid(), "context": CONTEXT,
            "devices": device_inventory() if devices is None else devices,
            "providers": providers, "selected": select_provider(providers)}


def collect(virgl_socket=None, inventory=False):
    """Public session integration seam; all subprocess work remains bounded."""
    return build_report(inventory=inventory, virgl_socket=virgl_socket)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--virgl-socket", type=validate_socket, help="explicit app-owned VirGL socket")
    parser.add_argument("--provider", choices=GL_PROVIDERS, help="internal isolated EGL child")
    args = parser.parse_args(argv)
    if args.provider:
        if args.provider == "virpipe" and not socket_available(args.virgl_socket):
            attempt = unavailable("virpipe", "VirGL socket unavailable", status="blocked")
        else:
            os.environ.clear()
            os.environ.update(provider_environment(args.provider, args.virgl_socket))
            from graphics_egl import probe
            attempt = validate_attempt(args.provider, {"id": args.provider, **probe()})
        report = {"schema": SCHEMA, "uid": os.getuid(), "context": CONTEXT,
                  "devices": [], "providers": [attempt], "selected": select_provider([attempt])}
    else:
        report = collect(virgl_socket=args.virgl_socket, inventory=args.inventory)
    document = json.dumps(report, ensure_ascii=True, separators=(",", ":"))
    if len(document.encode("utf-8")) >= OUTPUT_LIMIT:
        raise RuntimeError("graphics report exceeds output bound")
    print(document)


if __name__ == "__main__":
    main()
