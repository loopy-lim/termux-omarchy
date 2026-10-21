// SPDX-License-Identifier: BSD-3-Clause
#pragma once
#include <aquamarine/allocator/Allocator.hpp>
#include <hyprutils/memory/WeakPtr.hpp>

namespace Aquamarine {
class CSHMBuffer final : public IBuffer {
public:
    ~CSHMBuffer() override;
    eBufferCapability caps() override;
    eBufferType type() override;
    void update(const Hyprutils::Math::CRegion& damage) override;
    bool isSynchronous() override;
    bool good() override;
    SSHMAttrs shm() override;
    std::tuple<uint8_t*, uint32_t, size_t> beginDataPtr(uint32_t flags) override;
    void endDataPtr() override;
private:
    explicit CSHMBuffer(const SAllocatorBufferParams& params);
    SSHMAttrs attrs{.fd = -1};
    uint8_t* mapping = nullptr;
    size_t length = 0;
    bool mappedForAccess = false;
    friend class CSHMAllocator;
};

class CSHMAllocator final : public IAllocator {
public:
    static Hyprutils::Memory::CSharedPointer<CSHMAllocator> create(
        Hyprutils::Memory::CWeakPointer<CBackend> backend);
    Hyprutils::Memory::CSharedPointer<IBuffer> acquire(const SAllocatorBufferParams& params,
        Hyprutils::Memory::CSharedPointer<CSwapchain> swapchain) override;
    Hyprutils::Memory::CSharedPointer<CBackend> getBackend() override;
    int drmFD() override;
    eAllocatorType type() override;
private:
    explicit CSHMAllocator(Hyprutils::Memory::CWeakPointer<CBackend> backend);
    Hyprutils::Memory::CWeakPointer<CBackend> backend;
};
}
