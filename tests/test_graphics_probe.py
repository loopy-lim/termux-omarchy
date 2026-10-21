"""Guest graphics evidence, bounded subprocesses, and real ctypes ABI contracts."""
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GUEST = ROOT / "guest/desktop/usr/local/lib/loopy"
PROBE = GUEST / "graphics_probe.py"


def load(name):
    path = GUEST / (name + ".py")
    if not path.is_file():
        raise AssertionError("guest graphics capability implementation is missing: " + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def result(provider="llvmpipe", renderer="llvmpipe (LLVM 19)", pixels=True):
    return {"id": provider, "status": "ready", "reason": "offscreen only",
            "renderer": renderer, "pixelVerified": pixels, "presentationVerified": False}


class GraphicsProbeTests(unittest.TestCase):
    def test_inventory_is_one_bounded_document_and_keeps_cairo_available(self):
        self.assertTrue(PROBE.is_file(), "guest graphics capability probe is missing")
        completed = subprocess.run([sys.executable, str(PROBE), "--inventory"],
                                   capture_output=True, text=True, timeout=3)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.count("\n"), 1)
        self.assertLess(len(completed.stdout.encode()), 16384)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["uid"], os.getuid())
        self.assertIn("offscreen", report["context"])
        self.assertEqual(report["selected"], "cairo")
        providers = {item["id"]: item for item in report["providers"]}
        self.assertEqual(providers["cairo"]["status"], "ready")
        self.assertEqual(providers["mesa-default"]["status"], "blocked")
        self.assertFalse(providers["cairo"]["pixelVerified"])
        for device in report["devices"]:
            self.assertEqual(set(device), {"path", "opened", "errno"})

    def test_selection_requires_pixels_and_the_requested_software_renderer(self):
        probe = load("graphics_probe")
        counterexamples = [result(pixels=False), result(renderer="Adreno 740"),
                           result(renderer="softpipe"), result(renderer="virpipe"),
                           result(renderer="Adreno (llvmpipe unavailable)"),
                           result(renderer="llvmpipe", pixels=1)]
        for attempt in counterexamples:
            with self.subTest(attempt=attempt):
                normalized = probe.validate_attempt("llvmpipe", attempt)
                self.assertEqual(normalized["status"], "failed")
                self.assertEqual(probe.select_provider([normalized]), "cairo")
        good = probe.validate_attempt("llvmpipe", result())
        self.assertEqual(probe.select_provider([good]), "llvmpipe")
        soft = probe.validate_attempt("softpipe", result("softpipe", "softpipe"))
        self.assertEqual(probe.select_provider([soft, good]), "llvmpipe")
        self.assertEqual(probe.select_provider([soft]), "softpipe")

    def test_mesa_pixels_never_claim_desktop_hardware_presentation(self):
        probe = load("graphics_probe")
        for renderer in ("Adreno 740", "llvmpipe (LLVM 19)", "virgl (Adreno)"):
            attempt = probe.validate_attempt("mesa-default", result("mesa-default", renderer))
            self.assertNotEqual(attempt["status"], "ready")
            self.assertEqual(probe.select_provider([attempt]), "cairo")
            self.assertTrue(attempt["pixelVerified"])

    def test_child_output_rejects_wrong_uid_schema_identity_and_malformed_json(self):
        probe = load("graphics_probe")
        valid = {"schema": 1, "uid": os.getuid(), "providers": [result()]}
        documents = ["{}", "not-json", json.dumps([valid]),
                     json.dumps({**valid, "schema": 2}),
                     json.dumps({**valid, "uid": os.getuid() + 1}),
                     json.dumps({**valid, "providers": [result("softpipe", "softpipe")]}),
                     json.dumps(valid) + "\nnoise", "x" * 16385]
        for document in documents:
            with self.subTest(document=document[:80]):
                attempt = probe.decode_attempt("llvmpipe", document)
                self.assertEqual(attempt["status"], "failed")
        self.assertEqual(probe.decode_attempt("llvmpipe", json.dumps(valid))["status"], "ready")

    def test_subprocess_deadline_and_output_limit_fail_without_leaking_process(self):
        probe = load("graphics_probe")
        for program, reason in (("import os,time; print(os.getpid(),flush=True); time.sleep(30)", "timeout"),
                                ("import os; os.write(1,b'x'*1000000)", "limit"),
                                ("import os; os.write(2,b'x'*1000000)", "limit")):
            with self.subTest(reason=reason):
                before = time.monotonic()
                child = probe.run_bounded([sys.executable, "-c", program], {}, timeout=.15)
                self.assertIn(reason, child["error"])
                self.assertLess(time.monotonic() - before, 2)
                self.assertLessEqual(len(child["stdout"]), 16384)
                if reason == "timeout":
                    with self.assertRaises(ProcessLookupError):
                        os.kill(int(child["stdout"]), 0)
        child = probe.run_bounded([sys.executable, "-c", "print('done')"], {}, timeout=1)
        self.assertEqual(child["error"], "")
        self.assertEqual(child["stdout"], "done\n")

    def test_provider_environment_drops_inherited_loader_and_version_overrides(self):
        probe = load("graphics_probe")
        inherited = {"LD_PRELOAD": "untrusted.so", "LD_LIBRARY_PATH": "/untrusted",
                     "MESA_GL_VERSION_OVERRIDE": "99.0", "DISPLAY": ":42",
                     "GALLIUM_DRIVER": "virpipe", "VK_ICD_FILENAMES": "/untrusted.json"}
        original = dict(os.environ)
        try:
            os.environ.update(inherited)
            software = probe.provider_environment("llvmpipe")
            self.assertEqual(software["GALLIUM_DRIVER"], "llvmpipe")
            self.assertEqual(software["LIBGL_ALWAYS_SOFTWARE"], "true")
            self.assertEqual(software["EGL_PLATFORM"], "surfaceless")
            for key in set(inherited) - {"GALLIUM_DRIVER"}:
                self.assertNotIn(key, software)
            self.assertNotIn("GALLIUM_DRIVER", probe.provider_environment("mesa-default"))
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_inventory_reports_actual_open_errno_not_dac_guess(self):
        probe = load("graphics_probe")
        with tempfile.TemporaryDirectory() as directory:
            available = Path(directory) / "device"
            available.write_bytes(b"")
            missing = Path(directory) / "missing"
            report = probe.device_inventory([str(available), str(missing)])
        self.assertEqual(report[0], {"path": str(available), "opened": True, "errno": 0})
        self.assertEqual(report[1]["errno"], 2)
        self.assertFalse(report[1]["opened"])

    def test_default_checks_at_most_two_software_children_and_stops_after_success(self):
        probe = load("graphics_probe")
        calls = []

        def failed(provider):
            calls.append(provider)
            return probe.validate_attempt(provider, result(provider, "wrong"))

        report = probe.build_report(prober=failed, devices=[])
        self.assertEqual(calls, ["llvmpipe", "softpipe"])
        self.assertEqual(report["selected"], "cairo")
        calls.clear()

        def ready(provider):
            calls.append(provider)
            return probe.validate_attempt(provider, result())

        report = probe.build_report(prober=ready, devices=[])
        self.assertEqual(calls, ["llvmpipe"])
        self.assertEqual(report["selected"], "llvmpipe")

    def test_collect_public_contract_never_reports_verified_presentation(self):
        probe = load("graphics_probe")
        self.assertTrue(callable(getattr(probe, "collect", None)), "public collect API is missing")
        report = probe.collect(inventory=True)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["selected"], "cairo")
        for provider in report["providers"]:
            self.assertIn(provider["status"], {"ready", "blocked", "failed"})
            self.assertIs(provider["presentationVerified"], False)

    def test_proxy_socket_is_explicit_validated_and_cannot_inject_environment(self):
        probe = load("graphics_probe")
        self.assertTrue(callable(getattr(probe, "validate_socket", None)), "validated VirGL socket API is missing")
        socket = "/run/loopy/virgl-test-123.sock"
        self.assertEqual(probe.validate_socket(socket), socket)
        invalid = ("/tmp/virgl-test.sock", "/run/loopy/../virgl-test.sock",
                   "/run/loopy/virgl-test.sock\nLD_PRELOAD=evil", "/run/loopy/virgl-.sock",
                   "/run/loopy/virgl-" + "a" * 65 + ".sock", "/run/loopy/virgl-test.sock/extra")
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises(ValueError): probe.validate_socket(path)
        environment = probe.provider_environment("virpipe", socket)
        self.assertEqual(environment["GALLIUM_DRIVER"], "virpipe")
        self.assertEqual(environment["LIBGL_ALWAYS_SOFTWARE"], "true")
        self.assertEqual(environment["VTEST_SOCKET_NAME"], socket)
        self.assertNotIn("LD_PRELOAD", environment)
        self.assertNotIn("VTEST_SOCKET_NAME", probe.provider_environment("llvmpipe"))

    def test_proxy_requires_virgl_pixels_and_never_changes_default_selection(self):
        probe = load("graphics_probe")
        proxy = probe.validate_attempt("virpipe", result("virpipe", "virgl (Adreno 740)"))
        self.assertEqual(proxy["status"], "ready")
        self.assertIs(proxy["presentationVerified"], False)
        self.assertEqual(probe.select_provider([proxy]), "cairo")
        for renderer, pixels in (("llvmpipe", True), ("softpipe", True),
                                 ("Adreno 740", True), ("virpipe", True), ("virgl", False)):
            with self.subTest(renderer=renderer, pixels=pixels):
                failed = probe.validate_attempt("virpipe", result("virpipe", renderer, pixels))
                self.assertEqual(failed["status"], "failed")

    def test_proxy_timeout_falls_through_both_software_candidates(self):
        probe = load("graphics_probe")
        self.assertTrue(callable(getattr(probe, "socket_available", None)), "VirGL socket inventory is missing")
        socket = "/run/loopy/virgl-test.sock"
        calls = []

        def attempts(provider, virgl_socket=None):
            calls.append((provider, virgl_socket))
            if provider == "softpipe": return result("softpipe", "softpipe")
            return dict(id=provider, renderer="", pixelVerified=False, reason="probe timeout")

        with mock.patch.object(probe, "socket_available", return_value=True):
            report = probe.build_report(virgl_socket=socket, prober=attempts, devices=[])
        self.assertEqual(calls, [("virpipe", socket), ("llvmpipe", None), ("softpipe", None)])
        self.assertEqual(report["selected"], "softpipe")
        proxy = next(item for item in report["providers"] if item["id"] == "virpipe")
        self.assertEqual(proxy["status"], "failed")
        self.assertIn("timeout", proxy["reason"])

    def test_no_socket_or_regular_file_never_claims_proxy_ready(self):
        probe = load("graphics_probe")
        self.assertTrue(callable(getattr(probe, "socket_available", None)), "VirGL socket inventory is missing")
        socket = "/run/loopy/virgl-test.sock"
        with mock.patch.object(probe.os, "lstat", return_value=type("Info", (), {"st_mode": stat.S_IFREG})()):
            self.assertFalse(probe.socket_available(socket))
        with mock.patch.object(probe, "socket_available", return_value=False):
            report = probe.build_report(virgl_socket=socket, inventory=True, devices=[])
        proxy = next(item for item in report["providers"] if item["id"] == "virpipe")
        self.assertEqual(proxy["status"], "blocked")
        self.assertFalse(proxy["pixelVerified"])

    def test_socket_symlink_is_not_an_app_owned_socket(self):
        probe = load("graphics_probe")
        socket = "/run/loopy/virgl-test.sock"
        with mock.patch.object(probe.os, "stat", return_value=type("Info", (), {"st_mode": stat.S_IFSOCK})()), \
             mock.patch.object(probe.os, "lstat", return_value=type("Info", (), {"st_mode": stat.S_IFLNK})()):
            self.assertFalse(probe.socket_available(socket))

    def test_ready_proxy_still_probes_cpu_and_child_receives_only_explicit_socket(self):
        probe = load("graphics_probe")
        socket = "/run/loopy/virgl-test.sock"
        calls = []

        def attempts(provider, virgl_socket=None):
            calls.append((provider, virgl_socket))
            return result(provider, "virgl (fixture)" if provider == "virpipe" else "llvmpipe")

        with mock.patch.object(probe, "socket_available", return_value=True):
            report = probe.build_report(virgl_socket=socket, prober=attempts, devices=[])
        self.assertEqual(calls, [("virpipe", socket), ("llvmpipe", None)])
        self.assertEqual(report["selected"], "llvmpipe")
        captured = []

        def child(command, environment):
            captured.append((command, environment))
            document = {"schema": 1, "uid": os.getuid(), "providers": [result("virpipe", "virgl")]}
            return {"stdout": json.dumps(document), "error": "", "returncode": 0}

        with mock.patch.object(probe, "run_bounded", side_effect=child):
            attempt = probe.probe_provider("virpipe", socket)
        self.assertEqual(attempt["status"], "ready")
        self.assertEqual(captured[0][0][-4:], ["--provider", "virpipe", "--virgl-socket", socket])
        self.assertEqual(captured[0][1]["VTEST_SOCKET_NAME"], socket)


STUB = r"""
#include <stdint.h>
#include <string.h>
#include <math.h>
static void *D=(void*)(uintptr_t)0x100000001ULL, *C=(void*)(uintptr_t)0x200000002ULL;
static void *S=(void*)(uintptr_t)0x300000003ULL, *X=(void*)(uintptr_t)0x400000004ULL;
int fail_step=0, cleanup=0, wrong_pixels=0, current=0, clear_ok=0;
unsigned int eglGetError(void) { return 0x3009; }
void *eglGetDisplay(void *native) { return native == 0 ? D : 0; }
unsigned int eglInitialize(void *d,int *major,int *minor) {
    if(d!=D || fail_step==1)return 0; *major=1; *minor=5; return 1;
}
unsigned int eglBindAPI(unsigned int api) { return api==0x30a0; }
unsigned int eglChooseConfig(void *d,const int *attrs,void **config,int max,int *count) {
    if(d!=D || max!=1 || attrs[0]!=0x3033 || attrs[1]!=1)return 0;
    *config=C; *count=1; return 1;
}
void *eglCreatePbufferSurface(void *d,void *c,const int *attrs) {
    return d==D && c==C && attrs[0]==0x3057 && attrs[1]==1 ? S : 0;
}
void *eglCreateContext(void *d,void *c,void *share,const int *attrs) {
    return d==D && c==C && !share && attrs[0]==0x3098 && attrs[1]==2 ? X : 0;
}
unsigned int eglMakeCurrent(void *d,void *draw,void *read,void *x) {
    if(d!=D || fail_step==2)return 0;
    if(!draw && !read && !x) { current=0; cleanup|=1; return 1; }
    current=draw==S && read==S && x==X; return current;
}
unsigned int eglDestroyContext(void *d,void *x) { if(d==D && x==X)cleanup|=2; return 1; }
unsigned int eglDestroySurface(void *d,void *s) { if(d==D && s==S)cleanup|=4; return 1; }
unsigned int eglTerminate(void *d) { if(d==D)cleanup|=8; return 1; }
const char *glGetString(unsigned int name) { return current && name==0x1f01 ? "llvmpipe (ABI fixture)" : 0; }
unsigned int glGetError(void) { return 0; }
void glClearColor(float r,float g,float b,float a) {
    clear_ok=fabsf(r-.2f)<.001f && fabsf(g-.4f)<.001f && fabsf(b-.6f)<.001f && a==1.f;
}
void glClear(unsigned int mask) { clear_ok=clear_ok && current && mask==0x4000; }
void glReadPixels(int x,int y,int w,int h,unsigned int format,unsigned int type,void *pixels) {
    unsigned char correct[4]={51,102,153,255};
    if(!current || !clear_ok || x || y || w!=1 || h!=1 || format!=0x1908 || type!=0x1401)return;
    memcpy(pixels,correct,4); if(wrong_pixels)((unsigned char*)pixels)[0]=0;
}
"""


@unittest.skipUnless(shutil.which("cc"), "host C compiler required")
class EGLABIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="loopy-graphics-abi-")
        cls.addClassCleanup(cls.workspace.cleanup)
        source = Path(cls.workspace.name) / "egl.c"
        cls.binary = source.with_suffix(".so")
        source.write_text(STUB)
        shared = "-dynamiclib" if sys.platform == "darwin" else "-shared"
        built = subprocess.run(["cc", shared, "-fPIC", str(source), "-o", str(cls.binary)],
                               capture_output=True, text=True, timeout=10)
        if built.returncode:
            raise AssertionError(built.stderr)

    def setUp(self):
        self.egl = load("graphics_egl")
        self.library = ctypes.CDLL(str(self.binary))
        for name in ("fail_step", "cleanup", "wrong_pixels", "current", "clear_ok"):
            ctypes.c_int.in_dll(self.library, name).value = 0

    def execute(self):
        return self.egl.probe(loader=lambda _name: self.library)

    def test_64_bit_egl_handles_float_arguments_and_actual_pixel_readback(self):
        attempt = self.execute()
        self.assertTrue(attempt["pixelVerified"], attempt)
        self.assertEqual(attempt["renderer"], "llvmpipe (ABI fixture)")
        self.assertEqual(ctypes.c_int.in_dll(self.library, "cleanup").value, 15)

    def test_failed_pixels_cannot_be_promoted_and_resources_are_destroyed(self):
        ctypes.c_int.in_dll(self.library, "wrong_pixels").value = 1
        attempt = self.execute()
        self.assertFalse(attempt["pixelVerified"])
        self.assertIn("pixel", attempt["reason"])
        self.assertEqual(ctypes.c_int.in_dll(self.library, "cleanup").value, 15)

    def test_egl_initialization_and_make_current_failures_keep_error_and_cleanup(self):
        for step, cleanup in ((1, 0), (2, 14)):
            ctypes.c_int.in_dll(self.library, "cleanup").value = 0
            ctypes.c_int.in_dll(self.library, "fail_step").value = step
            attempt = self.execute()
            self.assertFalse(attempt["pixelVerified"])
            self.assertIn("0x3009", attempt["reason"])
            self.assertEqual(ctypes.c_int.in_dll(self.library, "cleanup").value, cleanup)


if __name__ == "__main__":
    unittest.main()
