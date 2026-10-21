#!/usr/bin/env python3
"""Apply acquire-fence hand-off support to an Aquamarine tree (post KGSL patch).

Adds:
  - IBuffer presentation acquire-fence FD slot
  - zwp_linux_explicit_synchronization_v1 client protocol codegen
  - CWaylandOutput::commit set_acquire_fence (poll-wait fallback)
"""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = 'setPresentationAcquireFence'


def patch_cmake(text: str) -> str:
    if 'linux-explicit-synchronization-unstable-v1' in text:
        return text
    needle = 'protocolnew("stable/linux-dmabuf" "linux-dmabuf-v1" false)\n'
    if needle not in text:
        raise SystemExit('CMakeLists.txt: linux-dmabuf protocol line not found')
    return text.replace(
        needle,
        needle
        + 'protocolnew("unstable/linux-explicit-synchronization" '
        + '"linux-explicit-synchronization-unstable-v1" false)\n',
        1,
    )


def patch_buffer_hpp(text: str) -> str:
    if MARKER in text:
        return text
    old = '''        void                                           setPresentationDMABUFActive(bool active);
        bool                                           presentationDMABUFActive() const;

        Hyprutils::Math::Vector2D                      size;
'''
    new = '''        void                                           setPresentationDMABUFActive(bool active);
        bool                                           presentationDMABUFActive() const;

        // Per-commit acquire fence (sync_file FD). Ownership transfers into
        // Aquamarine on takePresentationAcquireFence(); Wayland backend may
        // pass it to the parent via set_acquire_fence.
        bool                                           setPresentationAcquireFence(int fd);
        int                                            takePresentationAcquireFence();
        void                                           clearPresentationAcquireFence();

        Hyprutils::Math::Vector2D                      size;
'''
    if old not in text:
        raise SystemExit('Buffer.hpp: presentation DMABUF active block not found')
    text = text.replace(old, new, 1)
    old_priv = '''        SDMABUFAttrs presentationDMABUFAttrs;
        bool        presentationDMABUFIsActive = false;
    };
'''
    new_priv = '''        SDMABUFAttrs presentationDMABUFAttrs;
        bool        presentationDMABUFIsActive = false;
        int         presentationAcquireFenceFd = -1;
    };
'''
    if old_priv not in text:
        raise SystemExit('Buffer.hpp: private presentation fields not found')
    return text.replace(old_priv, new_priv, 1)


def patch_buffer_cpp(text: str) -> str:
    if MARKER in text:
        return text
    old_dtor = 'IBuffer::~IBuffer() {\n    clearPresentationDMABUF();\n    attachments.clear();\n}'
    new_dtor = (
        'IBuffer::~IBuffer() {\n    clearPresentationDMABUF();\n'
        '    clearPresentationAcquireFence();\n    attachments.clear();\n}'
    )
    if old_dtor not in text:
        raise SystemExit('Buffer.cpp: destructor clearPresentationDMABUF missing')
    text = text.replace(old_dtor, new_dtor, 1)
    return text.rstrip() + '''

bool Aquamarine::IBuffer::setPresentationAcquireFence(int fd) {
    clearPresentationAcquireFence();
    if (fd < 0)
        return false;
    presentationAcquireFenceFd = fd;
    return true;
}

int Aquamarine::IBuffer::takePresentationAcquireFence() {
    const int fd = presentationAcquireFenceFd;
    presentationAcquireFenceFd = -1;
    return fd;
}

void Aquamarine::IBuffer::clearPresentationAcquireFence() {
    if (presentationAcquireFenceFd >= 0)
        close(presentationAcquireFenceFd);
    presentationAcquireFenceFd = -1;
}
'''


def patch_wayland_hpp(text: str) -> str:
    if 'linux-explicit-synchronization-unstable-v1.hpp' in text:
        return text
    if '#include <linux-dmabuf-v1.hpp>' not in text:
        raise SystemExit('Wayland.hpp: linux-dmabuf include missing')
    text = text.replace(
        '#include <linux-dmabuf-v1.hpp>\n',
        '#include <linux-dmabuf-v1.hpp>\n#include <linux-explicit-synchronization-unstable-v1.hpp>\n',
        1,
    )
    old_out = '''            Hyprutils::Memory::CSharedPointer<CCWlCallback>  frameCallback;
            Hyprutils::Math::Vector2D                        surfaceSize;
            Hyprutils::Math::Vector2D                        pendingConfigureSize;
            bool                                             configured = false;
        } waylandState;
'''
    new_out = '''            Hyprutils::Memory::CSharedPointer<CCWlCallback>  frameCallback;
            Hyprutils::Memory::CSharedPointer<CCZwpLinuxSurfaceSynchronizationV1> surfaceSync;
            Hyprutils::Math::Vector2D                        surfaceSize;
            Hyprutils::Math::Vector2D                        pendingConfigureSize;
            bool                                             configured = false;
        } waylandState;
'''
    if old_out not in text:
        raise SystemExit('Wayland.hpp: output waylandState block not found')
    text = text.replace(old_out, new_out, 1)
    old_be = '''            Hyprutils::Memory::CSharedPointer<CCZwpLinuxDmabufV1>         dmabuf;
            Hyprutils::Memory::CSharedPointer<CCZwpLinuxDmabufFeedbackV1> dmabufFeedback;

            // control
            bool dmabufFailed = false;
        } waylandState;
'''
    new_be = '''            Hyprutils::Memory::CSharedPointer<CCZwpLinuxDmabufV1>         dmabuf;
            Hyprutils::Memory::CSharedPointer<CCZwpLinuxDmabufFeedbackV1> dmabufFeedback;
            Hyprutils::Memory::CSharedPointer<CCZwpLinuxExplicitSynchronizationV1> explicitSync;

            // control
            bool dmabufFailed = false;
        } waylandState;
'''
    if old_be not in text:
        raise SystemExit('Wayland.hpp: backend waylandState block not found')
    return text.replace(old_be, new_be, 1)


def patch_wayland_cpp(text: str) -> str:
    if (
        'sendSetAcquireFence' in text
        and 'zwp_linux_explicit_synchronization_v1' in text
        and 'if (!initDmabuf()) {\n                backend->log(AQ_LOG_ERROR, "Wayland backend cannot start: zwp_linux_dmabuf_v1 init failed");\n                waylandState.dmabufFailed = true;\n            }\n        } else if (NAME == "zwp_linux_explicit_synchronization_v1")' in text
    ):
        return text

    if '#include <poll.h>' not in text:
        text = text.replace('#include <unistd.h>\n', '#include <unistd.h>\n#include <poll.h>\n', 1)

    old_dmabuf = '''        } else if (NAME == "zwp_linux_dmabuf_v1") {
            const auto bindVersion = std::min(version, 4U);
            TRACE(backend->log(AQ_LOG_TRACE, std::format("  > binding to global: {} (version {}) with id {}", name, bindVersion, id)));
            waylandState.dmabuf = makeShared<CCZwpLinuxDmabufV1>(
                (wl_proxy*)wl_registry_bind((wl_registry*)waylandState.registry->resource(), id, &zwp_linux_dmabuf_v1_interface, bindVersion));
            if (!initDmabuf()) {
                backend->log(AQ_LOG_ERROR, "Wayland backend cannot start: zwp_linux_dmabuf_v1 init failed");
                waylandState.dmabufFailed = true;
            }
        }
'''
    new_dmabuf = '''        } else if (NAME == "zwp_linux_dmabuf_v1") {
            const auto bindVersion = std::min(version, 4U);
            TRACE(backend->log(AQ_LOG_TRACE, std::format("  > binding to global: {} (version {}) with id {}", name, bindVersion, id)));
            waylandState.dmabuf = makeShared<CCZwpLinuxDmabufV1>(
                (wl_proxy*)wl_registry_bind((wl_registry*)waylandState.registry->resource(), id, &zwp_linux_dmabuf_v1_interface, bindVersion));
            if (!initDmabuf()) {
                backend->log(AQ_LOG_ERROR, "Wayland backend cannot start: zwp_linux_dmabuf_v1 init failed");
                waylandState.dmabufFailed = true;
            }
        } else if (NAME == "zwp_linux_explicit_synchronization_v1") {
            const auto bindVersion = std::min(version, 2U);
            TRACE(backend->log(AQ_LOG_TRACE, std::format("  > binding to global: {} (version {}) with id {}", name, bindVersion, id)));
            waylandState.explicitSync = makeShared<CCZwpLinuxExplicitSynchronizationV1>(
                (wl_proxy*)wl_registry_bind((wl_registry*)waylandState.registry->resource(), id,
                                            &zwp_linux_explicit_synchronization_v1_interface, bindVersion));
        }
'''
    if old_dmabuf not in text:
        raise SystemExit(
            'Wayland.cpp: clean zwp_linux_dmabuf_v1 bind block not found; '
            'reset Wayland.cpp to post-am KGSL state and re-run'
        )
    text = text.replace(old_dmabuf, new_dmabuf, 1)

    if 'got zwp_linux_surface_synchronization_v1' not in text:
        old_surf = '''    waylandState.surface = makeShared<CCWlSurface>(backend->waylandState.compositor->sendCreateSurface());

    if (!waylandState.surface->resource()) {
        backend->backend->log(AQ_LOG_ERROR, std::format("Output {} failed: no surface given. Errno: {}", name, errno));
        return;
    }
'''
        new_surf = '''    waylandState.surface = makeShared<CCWlSurface>(backend->waylandState.compositor->sendCreateSurface());

    if (!waylandState.surface->resource()) {
        backend->backend->log(AQ_LOG_ERROR, std::format("Output {} failed: no surface given. Errno: {}", name, errno));
        return;
    }

    if (backend->waylandState.explicitSync) {
        waylandState.surfaceSync = makeShared<CCZwpLinuxSurfaceSynchronizationV1>(
            backend->waylandState.explicitSync->sendGetSynchronization(waylandState.surface->resource()));
        if (waylandState.surfaceSync && waylandState.surfaceSync->resource())
            backend->backend->log(AQ_LOG_DEBUG, std::format("Output {}: got zwp_linux_surface_synchronization_v1", name));
        else {
            waylandState.surfaceSync.reset();
            backend->backend->log(AQ_LOG_WARNING, std::format("Output {}: get_synchronization failed", name));
        }
    }
'''
        if old_surf not in text:
            raise SystemExit('Wayland.cpp: surface create block not found')
        text = text.replace(old_surf, new_surf, 1)

    old_finish = '''    // KGSL does not publish DRM implicit-sync fences for a DMA heap import in
    // every driver path. This diagnostic/compatibility switch establishes the
    // synchronization boundary before the parent compositor samples it. Once
    // validated, this can be replaced by a native fence hand-off.
    if (state->internalState.buffer->type() == BUFFER_TYPE_DMABUF && envEnabled("AQ_ANDROID_DMABUF_GLFINISH"))
        glFinish();

    waylandState.surface->sendAttach(wlBuffer->waylandState.buffer.get(), 0, 0);
'''
    new_finish = '''    // Prefer parent-side GPU wait via acquire fence. Fall back to poll(sync_file)
    // when explicit-sync is unavailable, and to AQ_ANDROID_DMABUF_GLFINISH only
    // when no fence was queued by the renderer.
    int  fenceFd   = state->internalState.buffer->takePresentationAcquireFence();
    int  sentFd    = -1;
    bool fenceSent = false;
    if (fenceFd >= 0 && waylandState.surfaceSync) {
        // libwayland takes ownership of the fd passed to a request and closes
        // it after the request is flushed. Send a dup so the original stays
        // ours to close deterministically below — no double-close, no leak.
        sentFd    = fcntl(fenceFd, F_DUPFD_CLOEXEC, 0);
        fenceSent = sentFd >= 0;
        if (fenceSent)
            waylandState.surfaceSync->sendSetAcquireFence(sentFd);
    }

    waylandState.surface->sendAttach(wlBuffer->waylandState.buffer.get(), 0, 0);
'''
    if old_finish not in text:
        raise SystemExit('Wayland.cpp: AQ_ANDROID_DMABUF_GLFINISH commit block not found')
    text = text.replace(old_finish, new_finish, 1)

    # Close both fence fds AFTER the stock wl_display_flush so weston has
    # already received the request (this libwayland build does not close
    # request fds itself — closing pre-flush froze the pipeline earlier).
    anchor = '''    wl_display_flush(backend->waylandState.display);

    events.commit.emit();
'''
    fence_close = '''    wl_display_flush(backend->waylandState.display);

    if (fenceFd >= 0) {
        if (!fenceSent) {
            // No explicit-sync on the parent: CPU-wait on the sync_file so the
            // compositor never samples the buffer before the GPU is done.
            pollfd pfd{.fd = fenceFd, .events = POLLIN, .revents = 0};
            while (true) {
                const int rc = poll(&pfd, 1, -1);
                if (rc > 0 || (rc < 0 && errno != EINTR))
                    break;
            }
        }
        // The dup sent into libwayland is never closed by this build; the
        // request was flushed above, so weston already owns its own copy.
        if (sentFd >= 0)
            close(sentFd);
        close(fenceFd);
    }

    events.commit.emit();
'''
    if anchor not in text:
        raise SystemExit('Wayland.cpp: post-flush anchor not found')
    text = text.replace(anchor, fence_close, 1)

    if 'waylandState.explicitSync.reset();' not in text:
        text = text.replace(
            'waylandState.dmabuf.reset();\n',
            'waylandState.explicitSync.reset();\n    waylandState.dmabuf.reset();\n',
            1,
        )
    return text


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: apply-aquamarine-handoff.py /path/to/aquamarine-source', file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    patches = [
        (root / 'CMakeLists.txt', patch_cmake),
        (root / 'include/aquamarine/buffer/Buffer.hpp', patch_buffer_hpp),
        (root / 'src/buffer/Buffer.cpp', patch_buffer_cpp),
        (root / 'include/aquamarine/backend/Wayland.hpp', patch_wayland_hpp),
        (root / 'src/backend/Wayland.cpp', patch_wayland_cpp),
    ]
    for path, fn in patches:
        text = path.read_text()
        new = fn(text)
        if new != text:
            path.write_text(new)
            print(path)
        else:
            print(f'unchanged {path}')
    if MARKER not in (root / 'include/aquamarine/buffer/Buffer.hpp').read_text():
        print('Buffer.hpp missing marker after apply', file=sys.stderr)
        return 1
    if 'sendSetAcquireFence' not in (root / 'src/backend/Wayland.cpp').read_text():
        print('Wayland.cpp missing set_acquire_fence after apply', file=sys.stderr)
        return 1
    # structural sanity: explicit sync must be sibling of dmabuf bind, not nested in initDmabuf
    wl = (root / 'src/backend/Wayland.cpp').read_text()
    if '} else if (NAME == "zwp_linux_explicit_synchronization_v1")' not in wl:
        print('Wayland.cpp: explicit-sync bind not chained correctly', file=sys.stderr)
        return 1
    if 'dmabufFailed = true;\n            } else if (NAME == "zwp_linux_explicit' in wl:
        print('Wayland.cpp: explicit-sync wrongly nested under initDmabuf', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
