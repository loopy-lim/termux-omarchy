// SPDX-License-Identifier: BSD-3-Clause
#include <aquamarine/allocator/SHM.hpp>
#include <aquamarine/backend/Backend.hpp>
#include <cmath>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

using namespace Aquamarine;
using Hyprutils::Memory::CSharedPointer;
using Hyprutils::Memory::CWeakPointer;

CSHMBuffer::CSHMBuffer(const SAllocatorBufferParams& params) {
    const auto width = params.size.x, height = params.size.y;
    if (!std::isfinite(width) || !std::isfinite(height) || width < 1 || height < 1
        || width > 8192 || height > 8192 || std::trunc(width) != width || std::trunc(height) != height
        || params.scanout || params.multigpu)
        return;
    const auto format = params.format == DRM_FORMAT_INVALID ? DRM_FORMAT_ARGB8888 : params.format;
    if (format != DRM_FORMAT_ARGB8888 && format != DRM_FORMAT_XRGB8888)
        return;
    const int stride = (static_cast<int>(width) * 4 + 63) & ~63;
    const uint64_t bytes = static_cast<uint64_t>(stride) * static_cast<uint64_t>(height);
    if (bytes > 64 * 1024 * 1024)
        return;
    attrs.fd = memfd_create("loopy-aquamarine-shm", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (attrs.fd < 0 || ftruncate(attrs.fd, static_cast<off_t>(bytes)) < 0
        || fcntl(attrs.fd, F_ADD_SEALS, F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_SEAL) < 0)
        return;
    void* data = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, attrs.fd, 0);
    if (data == MAP_FAILED)
        return;
    mapping = static_cast<uint8_t*>(data);
    length = bytes;
    size = params.size;
    opaque = format == DRM_FORMAT_XRGB8888;
    attrs.success = true;
    attrs.size = size;
    attrs.format = format;
    attrs.stride = stride;
}

CSHMBuffer::~CSHMBuffer() {
    events.destroy.emit();
    if (mapping) munmap(mapping, length);
    if (attrs.fd >= 0) close(attrs.fd);
}

eBufferCapability CSHMBuffer::caps() { return BUFFER_CAPABILITY_DATAPTR; }
eBufferType CSHMBuffer::type() { return BUFFER_TYPE_SHM; }
void CSHMBuffer::update(const Hyprutils::Math::CRegion&) { }
bool CSHMBuffer::isSynchronous() { return true; }
bool CSHMBuffer::good() { return attrs.success && mapping && attrs.fd >= 0; }
SSHMAttrs CSHMBuffer::shm() { return attrs; }

std::tuple<uint8_t*, uint32_t, size_t> CSHMBuffer::beginDataPtr(uint32_t) {
    if (!good() || backendPinCount() != 0 || mappedForAccess)
        return {nullptr, 0, 0};
    mappedForAccess = true;
    return {mapping, attrs.format, length};
}
void CSHMBuffer::endDataPtr() { mappedForAccess = false; }

CSharedPointer<CSHMAllocator> CSHMAllocator::create(CWeakPointer<CBackend> backend) {
    return CSharedPointer<CSHMAllocator>(new CSHMAllocator(backend));
}
CSHMAllocator::CSHMAllocator(CWeakPointer<CBackend> backend_) : backend(backend_) { }
CSharedPointer<IBuffer> CSHMAllocator::acquire(const SAllocatorBufferParams& params, CSharedPointer<CSwapchain>) {
    auto buffer = CSharedPointer<IBuffer>(new CSHMBuffer(params));
    if (!buffer->good()) return nullptr;
    return buffer;
}
CSharedPointer<CBackend> CSHMAllocator::getBackend() { return backend.lock(); }
int CSHMAllocator::drmFD() { return -1; }
eAllocatorType CSHMAllocator::type() { return AQ_ALLOCATOR_TYPE_SHM; }
