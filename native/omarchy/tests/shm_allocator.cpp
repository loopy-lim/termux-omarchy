// SPDX-License-Identifier: BSD-3-Clause
// Exercise real Aquamarine allocation without a DRM node or a privileged user.
#include <aquamarine/backend/Backend.hpp>
#include <aquamarine/allocator/Allocator.hpp>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <sys/stat.h>
#include <unistd.h>

using namespace Aquamarine;
static int fail(const char* reason) { std::fprintf(stderr, "SHM allocator: %s\n", reason); return 1; }

int main() {
    setenv("AQ_SHM_ONLY", "1", 1);
    SBackendImplementationOptions implementation;
    implementation.backendType = AQ_BACKEND_HEADLESS;
    implementation.backendRequestMode = AQ_BACKEND_REQUEST_MANDATORY;
    SBackendOptions options;
    options.logFunction = [](eBackendLogLevel level, std::string text) {
        if (level >= AQ_LOG_ERROR) std::fprintf(stderr, "%s\n", text.c_str());
    };
    auto backend = CBackend::create({implementation}, options);
    if (!backend || !backend->start()) return fail("DRM-free backend has no working allocator");
    auto allocator = backend->primaryAllocator;
    if (!allocator || allocator->drmFD() != -1) return fail("unexpected DRM dependency");
    for (const auto& format : backend->getImplementations().at(0)->getRenderFormats())
        if (format.drmFormat != DRM_FORMAT_ARGB8888 && format.drmFormat != DRM_FORMAT_XRGB8888)
            return fail("incompatible render formats falsely advertised");
    auto buffer = allocator->acquire(SAllocatorBufferParams{.size = {3, 2}}, nullptr);
    if (!buffer || !buffer->good() || buffer->type() != BUFFER_TYPE_SHM || buffer->dmabuf().success)
        return fail("not a real SHM buffer");
    auto attrs = buffer->shm();
    struct stat state{};
    if (!attrs.success || attrs.fd < 0 || attrs.format != DRM_FORMAT_ARGB8888 || attrs.stride < 12
        || fstat(attrs.fd, &state) || state.st_size != attrs.stride * 2) return fail("invalid shared memory extent");
    if (!(fcntl(attrs.fd, F_GETFD) & FD_CLOEXEC)
        || (fcntl(attrs.fd, F_GET_SEALS) & (F_SEAL_SHRINK | F_SEAL_GROW)) != (F_SEAL_SHRINK | F_SEAL_GROW))
        return fail("unprotected shared memory descriptor");
    auto [pixels, format, length] = buffer->beginDataPtr(0);
    if (!pixels || format != attrs.format || length != static_cast<size_t>(state.st_size)) return fail("bad mapping");
    for (size_t i = 0; i < length; ++i) if (pixels[i] != 0) return fail("uninitialized pixels exposed");
    const unsigned char fixture[] = {0x12, 0x34, 0x56, 0x78};
    std::memcpy(pixels, fixture, 4);
    unsigned char readback[4]{};
    if (pread(attrs.fd, readback, 4, 0) != 4 || std::memcmp(readback, fixture, 4)) return fail("FD and mapping disagree");
    buffer->endDataPtr();
    buffer->backendPin();
    if (std::get<0>(buffer->beginDataPtr(0))) return fail("in-flight parent buffer is writable");
    buffer->backendUnpin();
    if (!std::get<0>(buffer->beginDataPtr(0))) return fail("released buffer cannot be reused");
    buffer->endDataPtr();
    const int descriptor = attrs.fd;
    buffer.reset();
    if (fcntl(descriptor, F_GETFD) != -1) return fail("descriptor leaked after buffer destruction");
    for (auto size : {Hyprutils::Math::Vector2D{0.0, 1.0}, {-1.0, 1.0}, {1.5, 1.0}, {8192.0, 8192.0},
                      {std::numeric_limits<double>::quiet_NaN(), 1.0}}) {
        if (allocator->acquire(SAllocatorBufferParams{.size = size}, nullptr)) return fail("invalid geometry accepted");
    }
    if (allocator->acquire(SAllocatorBufferParams{.size = {3, 2}, .format = DRM_FORMAT_XRGB2101010}, nullptr)
        || allocator->acquire(SAllocatorBufferParams{.size = {3, 2}, .scanout = true}, nullptr))
        return fail("unsupported HDR/scanout falsely advertised");
    std::printf("SHM allocator passed uid=%u: real pixels, FD seals, release ownership, lifetime, bounds\n", getuid());
    return 0;
}
