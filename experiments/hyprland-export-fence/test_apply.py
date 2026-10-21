#!/usr/bin/env python3
"""Host-side gate for apply.py / apply-aquamarine-handoff.py (no device rebuild)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APPLY = ROOT / 'apply.py'
APPLY_AQ = ROOT / 'apply-aquamarine-handoff.py'

BASE = '''void CGLRenderbuffer::unbind() {
    const auto outputBuffer = m_hlBuffer.lock();
    if (m_gpuExported && outputBuffer && outputBuffer->presentationDMABUFActive()) {
        // The current KGSL stack does not attach implicit DMA-BUF fences.
        // Finish the GPU work before the parent compositor samples the
        // exported texture. This removes the full-frame CPU readback while a
        // native-fence hand-off is implemented as the next optimization.
        glFinish();
        GLFB(m_framebuffer)->unbind();
        return;
    }
}
'''

PROBE = '''void CGLRenderbuffer::unbind() {
    const auto outputBuffer = m_hlBuffer.lock();
    if (m_gpuExported && outputBuffer && outputBuffer->presentationDMABUFActive()) {
        // The current KGSL stack does not attach implicit DMA-BUF fences.
        // Finish the GPU work before the parent compositor samples the
        // exported texture. This removes the full-frame CPU readback while a
        // native-fence hand-off is implemented as the next optimization.
        //
        // Loopy export-fence probe (experiments/hyprland-export-fence):
        static const bool exportProfile = Env::envEnabled("HYPRLAND_GL_EXPORT_PROFILE");
        static const bool fenceProbe    = Env::envEnabled("HYPRLAND_GL_NATIVE_FENCE_PROBE");
        glFinish();
        GLFB(m_framebuffer)->unbind();
        return;
    }
}
'''


class ApplyExportFence(unittest.TestCase):
    def _tree(self, text: str) -> Path:
        root = Path(tempfile.mkdtemp())
        path = root / 'src/render/gl/GLRenderbuffer.cpp'
        path.parent.mkdir(parents=True)
        path.write_text(text)
        return root

    def test_applies_handoff_from_base(self):
        tree = self._tree(BASE)
        self.assertEqual(subprocess.run(['python3', str(APPLY), str(tree)], check=False).returncode, 0)
        out = (tree / 'src/render/gl/GLRenderbuffer.cpp').read_text()
        self.assertIn('HYPRLAND_GL_EXPORT_HANDOFF', out)
        self.assertIn('setPresentationAcquireFence', out)
        self.assertIn('export fence-handoff:', out)
        self.assertIn('/tmp/loopy-export-profile.log', out)
        self.assertIn('glFinish();', out)  # fallback path kept
        self.assertEqual(subprocess.run(['python3', str(APPLY), str(tree)], check=False).returncode, 1)

    def test_applies_handoff_over_probe(self):
        tree = self._tree(PROBE)
        self.assertEqual(subprocess.run(['python3', str(APPLY), str(tree)], check=False).returncode, 0)
        out = (tree / 'src/render/gl/GLRenderbuffer.cpp').read_text()
        self.assertIn('HYPRLAND_GL_EXPORT_HANDOFF', out)
        self.assertNotIn('HYPRLAND_GL_NATIVE_FENCE_PROBE', out)

    def test_rejects_unpatched_tree(self):
        tree = self._tree('void CGLRenderbuffer::unbind() {}\n')
        self.assertEqual(subprocess.run(['python3', str(APPLY), str(tree)], check=False).returncode, 1)


class ApplyAquamarineHandoff(unittest.TestCase):
    def _aq_tree(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / 'CMakeLists.txt').write_text(
            'protocolwayland()\n\n'
            'protocolnew("stable/xdg-shell" "xdg-shell" false)\n'
            'protocolnew("stable/linux-dmabuf" "linux-dmabuf-v1" false)\n'
            '\n# Generate hwdata info\n'
        )
        buf_hpp = root / 'include/aquamarine/buffer/Buffer.hpp'
        buf_hpp.parent.mkdir(parents=True)
        buf_hpp.write_text('''
        void                                           setPresentationDMABUFActive(bool active);
        bool                                           presentationDMABUFActive() const;

        Hyprutils::Math::Vector2D                      size;
        bool                                           opaque          = false;

        struct {
            Hyprutils::Signal::CSignalT<> destroy;
        } events;

      private:
        int         locks = 0;
        SDMABUFAttrs presentationDMABUFAttrs;
        bool        presentationDMABUFIsActive = false;
    };
''')
        buf_cpp = root / 'src/buffer/Buffer.cpp'
        buf_cpp.parent.mkdir(parents=True)
        buf_cpp.write_text('''#include <aquamarine/buffer/Buffer.hpp>
#include <unistd.h>
IBuffer::~IBuffer() {
    clearPresentationDMABUF();
    attachments.clear();
}
bool Aquamarine::IBuffer::presentationDMABUFActive() const {
    return presentationDMABUFIsActive;
}
''')
        wl_hpp = root / 'include/aquamarine/backend/Wayland.hpp'
        wl_hpp.parent.mkdir(parents=True)
        wl_hpp.write_text('''#include <linux-dmabuf-v1.hpp>
            Hyprutils::Memory::CSharedPointer<CCWlCallback>  frameCallback;
            Hyprutils::Math::Vector2D                        surfaceSize;
            Hyprutils::Math::Vector2D                        pendingConfigureSize;
            bool                                             configured = false;
        } waylandState;

            Hyprutils::Memory::CSharedPointer<CCZwpLinuxDmabufV1>         dmabuf;
            Hyprutils::Memory::CSharedPointer<CCZwpLinuxDmabufFeedbackV1> dmabufFeedback;

            // control
            bool dmabufFailed = false;
        } waylandState;
''')
        wl_cpp = root / 'src/backend/Wayland.cpp'
        wl_cpp.parent.mkdir(parents=True)
        wl_cpp.write_text('''#include <unistd.h>
        } else if (NAME == "zwp_linux_dmabuf_v1") {
            const auto bindVersion = std::min(version, 4U);
            TRACE(backend->log(AQ_LOG_TRACE, std::format("  > binding to global: {} (version {}) with id {}", name, bindVersion, id)));
            waylandState.dmabuf = makeShared<CCZwpLinuxDmabufV1>(
                (wl_proxy*)wl_registry_bind((wl_registry*)waylandState.registry->resource(), id, &zwp_linux_dmabuf_v1_interface, bindVersion));
            if (!initDmabuf()) {
                backend->log(AQ_LOG_ERROR, "Wayland backend cannot start: zwp_linux_dmabuf_v1 init failed");
                waylandState.dmabufFailed = true;
            }
        }
    });
    waylandState.surface = makeShared<CCWlSurface>(backend->waylandState.compositor->sendCreateSurface());

    if (!waylandState.surface->resource()) {
        backend->backend->log(AQ_LOG_ERROR, std::format("Output {} failed: no surface given. Errno: {}", name, errno));
        return;
    }

    // KGSL does not publish DRM implicit-sync fences for a DMA heap import in
    // every driver path. This diagnostic/compatibility switch establishes the
    // synchronization boundary before the parent compositor samples it. Once
    // validated, this can be replaced by a native fence hand-off.
    if (state->internalState.buffer->type() == BUFFER_TYPE_DMABUF && envEnabled("AQ_ANDROID_DMABUF_GLFINISH"))
        glFinish();

    waylandState.surface->sendAttach(wlBuffer->waylandState.buffer.get(), 0, 0);
    waylandState.surface->sendCommit();
    waylandState.surfaceSize = state->internalState.buffer->size;

    // Flush immediately: commit() runs from the consumer's render path, outside
    // dispatchEvents() (which flushes only at its top).
    wl_display_flush(backend->waylandState.display);

    events.commit.emit();
    state->onCommit();
    needsFrame = false;

    return true;
}
''')
        return root

    def test_aquamarine_handoff(self):
        tree = self._aq_tree()
        self.assertEqual(subprocess.run(['python3', str(APPLY_AQ), str(tree)], check=False).returncode, 0)
        self.assertIn('linux-explicit-synchronization-unstable-v1',
                      (tree / 'CMakeLists.txt').read_text())
        self.assertIn('setPresentationAcquireFence',
                      (tree / 'include/aquamarine/buffer/Buffer.hpp').read_text())
        self.assertIn('sendSetAcquireFence', (tree / 'src/backend/Wayland.cpp').read_text())
        self.assertIn('zwp_linux_explicit_synchronization_v1',
                      (tree / 'src/backend/Wayland.cpp').read_text())
        # idempotent
        self.assertEqual(subprocess.run(['python3', str(APPLY_AQ), str(tree)], check=False).returncode, 0)


if __name__ == '__main__':
    unittest.main()
