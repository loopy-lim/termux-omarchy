#!/usr/bin/env python3
"""Apply export-path acquire-fence hand-off to a Hyprland source tree.

The tree must already include the Omarchy Android KGSL presentation patch
(CGLRenderbuffer::unbind export early-return with glFinish).

When HYPRLAND_GL_EXPORT_HANDOFF=1 and a native fence FD can be queued on the
presentation buffer, glFinish is skipped. Aquamarine must pass that FD via
set_acquire_fence (see apply-aquamarine-handoff.py). Otherwise glFinish stays.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER = 'HYPRLAND_GL_EXPORT_HANDOFF'
PROFILE_PATH = '/tmp/loopy-export-profile.log'

BASE_OLD = '''    const auto outputBuffer = m_hlBuffer.lock();
    if (m_gpuExported && outputBuffer && outputBuffer->presentationDMABUFActive()) {
        // The current KGSL stack does not attach implicit DMA-BUF fences.
        // Finish the GPU work before the parent compositor samples the
        // exported texture. This removes the full-frame CPU readback while a
        // native-fence hand-off is implemented as the next optimization.
        glFinish();
        GLFB(m_framebuffer)->unbind();
        return;
    }
'''

HANDOFF = r'''    const auto outputBuffer = m_hlBuffer.lock();
    if (m_gpuExported && outputBuffer && outputBuffer->presentationDMABUFActive()) {
        // GPU hand-off: create→flush→dup native fence, queue FD on the
        // presentation buffer for Aquamarine set_acquire_fence. Skip glFinish
        // only when HANDOFF is enabled and the FD was queued; otherwise keep
        // Finish as the synchronization barrier.
        static const bool exportProfile = Env::envEnabled("HYPRLAND_GL_EXPORT_PROFILE");
        static const bool handoff       = Env::envEnabled("HYPRLAND_GL_EXPORT_HANDOFF");
        static const bool forceFinish   = Env::envEnabled("HYPRLAND_GL_EXPORT_FORCE_FINISH");

        auto loopyProfileLog = [](const char* line) {
            FILE* f = fopen("/tmp/loopy-export-profile.log", "a");
            if (!f)
                return;
            fputs(line, f);
            fputc('\n', f);
            fflush(f);
            fclose(f);
        };

        bool skippedFinish = false;
        uint64_t finishUs = 0;

        if (handoff && !forceFinish && g_pHyprOpenGL->m_proc.eglCreateSyncKHR &&
            g_pHyprOpenGL->m_proc.eglDupNativeFenceFDANDROID) {
            const EGLint syncAttrs[] = {EGL_NONE};
            EGLSyncKHR sync = g_pHyprOpenGL->m_proc.eglCreateSyncKHR(
                g_pHyprOpenGL->m_eglDisplay, EGL_SYNC_NATIVE_FENCE_ANDROID, syncAttrs);
            if (sync != EGL_NO_SYNC_KHR) {
                glFlush();
                const int fenceFd = g_pHyprOpenGL->m_proc.eglDupNativeFenceFDANDROID(
                    g_pHyprOpenGL->m_eglDisplay, sync);
                if (fenceFd >= 0) {
                    if (outputBuffer->setPresentationAcquireFence(fenceFd))
                        skippedFinish = true;
                    else
                        close(fenceFd);
                }
                if (g_pHyprOpenGL->m_proc.eglDestroySyncKHR)
                    g_pHyprOpenGL->m_proc.eglDestroySyncKHR(g_pHyprOpenGL->m_eglDisplay, sync);
            }
        }

        if (!skippedFinish) {
            const auto started = std::chrono::steady_clock::now();
            glFinish();
            finishUs = std::chrono::duration_cast<std::chrono::microseconds>(
                           std::chrono::steady_clock::now() - started)
                           .count();
        }

        if (exportProfile) {
            static uint64_t frameCount   = 0;
            static uint64_t handoffOk    = 0;
            static uint64_t finishFrames = 0;
            static uint64_t totalFinishUs = 0;
            if (skippedFinish)
                ++handoffOk;
            else {
                ++finishFrames;
                totalFinishUs += finishUs;
            }
            if (++frameCount % 120 == 0) {
                char buf[320];
                const uint64_t avgFinish =
                    finishFrames ? (totalFinishUs / finishFrames) : 0;
                snprintf(buf, sizeof(buf),
                         "export fence-handoff: ok=%llu finish_fallback=%llu "
                         "avg_finish_us=%llu over %llu frames",
                         (unsigned long long)handoffOk,
                         (unsigned long long)finishFrames,
                         (unsigned long long)avgFinish,
                         (unsigned long long)frameCount);
                loopyProfileLog(buf);
            }
        }
        GLFB(m_framebuffer)->unbind();
        return;
    }
'''


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: apply.py /path/to/hyprland-source', file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    path = root / 'src/render/gl/GLRenderbuffer.cpp'
    text = path.read_text()
    if MARKER in text:
        print('already applied (handoff)', file=sys.stderr)
        return 1
    if '#include <cstdio>' not in text:
        if '#include <unistd.h>' in text:
            text = text.replace('#include <unistd.h>', '#include <unistd.h>\n#include <cstdio>')
        else:
            text = '#include <cstdio>\n' + text

    if BASE_OLD in text:
        text = text.replace(BASE_OLD, HANDOFF, 1)
    elif 'presentationDMABUFActive()' in text and 'glFinish();' in text:
        # Replace any prior probe body between the export if and unbind return.
        pattern = re.compile(
            r'(    const auto outputBuffer = m_hlBuffer\.lock\(\);\n'
            r'    if \(m_gpuExported && outputBuffer && outputBuffer->presentationDMABUFActive\(\)\) \{\n)'
            r'.*?'
            r'(        GLFB\(m_framebuffer\)->unbind\(\);\n'
            r'        return;\n'
            r'    }\n)',
            re.S,
        )
        new_text, n = pattern.subn(HANDOFF, text, count=1)
        if n != 1:
            print('export presentation block not found; reset file to post-am state first',
                  file=sys.stderr)
            return 1
        text = new_text
    else:
        print('base presentation export block not found; reset file to post-am state first',
              file=sys.stderr)
        return 1

    path.write_text(text)
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
