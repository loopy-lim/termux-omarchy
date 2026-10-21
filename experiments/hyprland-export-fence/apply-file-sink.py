#!/usr/bin/env python3
"""Rewrite probe logging to a dedicated file (Hyprland Log::INFO sink is silent).

Run on a tree that already has apply.py (HYPRLAND_GL_EXPORT_PROFILE present).
Writes lines to /run/user/1000/loopy-export-profile.log (guest path → Termux lr/).
"""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = 'loopy-export-profile.log'
NEEDLE_START = '        static const bool exportProfile = Env::envEnabled("HYPRLAND_GL_EXPORT_PROFILE");'
# Replace from exportProfile statics through end of export early-return body
OLD_TAIL_START = NEEDLE_START

NEW_BLOCK = r'''        static const bool exportProfile = Env::envEnabled("HYPRLAND_GL_EXPORT_PROFILE");
        static const bool fenceProbe    = Env::envEnabled("HYPRLAND_GL_NATIVE_FENCE_PROBE");

        // File sink: Hyprland's Log::INFO often never reaches hyprland.log here
        // (enable_stdout_logs=false and empty instance log). Always append when
        // either probe switch is on so GPU-path cost is observable.
        auto loopyProfileLog = [](const char* line) {
            FILE* f = fopen("/run/user/1000/loopy-export-profile.log", "a");
            if (!f)
                return;
            fputs(line, f);
            fputc('\n', f);
            fflush(f);
            fclose(f);
        };

        if (fenceProbe) {
            static uint64_t probeOk   = 0;
            static uint64_t probeFail = 0;
            const EGLint syncAttrs[] = {EGL_NONE};
            EGLSyncKHR sync = EGL_NO_SYNC_KHR;
            if (g_pHyprOpenGL->m_proc.eglCreateSyncKHR)
                sync = g_pHyprOpenGL->m_proc.eglCreateSyncKHR(
                    g_pHyprOpenGL->m_eglDisplay, EGL_SYNC_NATIVE_FENCE_ANDROID, syncAttrs);
            if (sync != EGL_NO_SYNC_KHR)
                glFlush();
            int fenceFd = -1;
            if (sync != EGL_NO_SYNC_KHR && g_pHyprOpenGL->m_proc.eglDupNativeFenceFDANDROID)
                fenceFd = g_pHyprOpenGL->m_proc.eglDupNativeFenceFDANDROID(
                    g_pHyprOpenGL->m_eglDisplay, sync);
            if (fenceFd >= 0) {
                ++probeOk;
                close(fenceFd);
            } else {
                ++probeFail;
            }
            if (sync != EGL_NO_SYNC_KHR && g_pHyprOpenGL->m_proc.eglDestroySyncKHR)
                g_pHyprOpenGL->m_proc.eglDestroySyncKHR(g_pHyprOpenGL->m_eglDisplay, sync);
            if ((probeOk + probeFail) % 120 == 0) {
                char buf[256];
                snprintf(buf, sizeof(buf),
                         "export native-fence probe: ok=%llu fail=%llu over %llu frames",
                         (unsigned long long)probeOk, (unsigned long long)probeFail,
                         (unsigned long long)(probeOk + probeFail));
                loopyProfileLog(buf);
                Log::logger->log(Log::INFO, "export native-fence probe: ok={} fail={} over {} frames",
                                 probeOk, probeFail, probeOk + probeFail);
            }
        }

        const auto started = std::chrono::steady_clock::now();
        glFinish();
        if (exportProfile) {
            static uint64_t frameCount = 0;
            static uint64_t totalUs    = 0;
            totalUs += std::chrono::duration_cast<std::chrono::microseconds>(
                           std::chrono::steady_clock::now() - started)
                           .count();
            if (++frameCount % 120 == 0) {
                char buf[256];
                snprintf(buf, sizeof(buf),
                         "export glFinish: avg %llu us over %llu frames",
                         (unsigned long long)(totalUs / frameCount),
                         (unsigned long long)frameCount);
                loopyProfileLog(buf);
                Log::logger->log(Log::INFO, "export glFinish: avg {} us over {} frames",
                                 totalUs / frameCount, frameCount);
            }
        }
        GLFB(m_framebuffer)->unbind();
        return;
    }
'''


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: apply-file-sink.py /path/to/hyprland-source', file=sys.stderr)
        return 2
    path = Path(sys.argv[1]) / 'src/render/gl/GLRenderbuffer.cpp'
    text = path.read_text()
    if MARKER in text:
        print('already has file sink', file=sys.stderr)
        return 1
    if 'HYPRLAND_GL_EXPORT_PROFILE' not in text:
        print('run apply.py first', file=sys.stderr)
        return 1
    # Find the probe block start and the early return that ends it
    start = text.find(OLD_TAIL_START)
    if start < 0:
        print('exportProfile static not found', file=sys.stderr)
        return 1
    end_marker = '        GLFB(m_framebuffer)->unbind();\n        return;\n    }\n'
    end = text.find(end_marker, start)
    if end < 0:
        print('export early-return end not found', file=sys.stderr)
        return 1
    end += len(end_marker)
    # Ensure cstdio available
    if '#include <cstdio>' not in text:
        text = text.replace('#include <unistd.h>', '#include <unistd.h>\n#include <cstdio>')
    new_text = text[:start] + NEW_BLOCK + text[end:]
    path.write_text(new_text)
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
