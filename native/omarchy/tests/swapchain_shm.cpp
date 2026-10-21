// SPDX-License-Identifier: BSD-3-Clause
#include <aquamarine/backend/Backend.hpp>
#include <aquamarine/allocator/Swapchain.hpp>
#include <cstdio>
#include <unistd.h>

using namespace Aquamarine;
static int fail(const char* reason) { std::fprintf(stderr, "SHM swapchain: %s\n", reason); return 1; }

int main() {
    setenv("AQ_SHM_ONLY", "1", 1);
    SBackendImplementationOptions implementation;
    implementation.backendType = AQ_BACKEND_HEADLESS;
    implementation.backendRequestMode = AQ_BACKEND_REQUEST_MANDATORY;
    auto backend = CBackend::create({implementation}, SBackendOptions{});
    if (!backend || !backend->start()) return fail("no allocator");
    auto swapchain = CSwapchain::create(backend->primaryAllocator, backend->getImplementations().at(0));
    if (!swapchain->reconfigure(SSwapchainOptions{.length = 3, .size = {3, 2}})) return fail("allocation");
    if (swapchain->currentOptions().format != DRM_FORMAT_ARGB8888) return fail("SHM format discarded");
    std::vector<Hyprutils::Memory::CSharedPointer<IBuffer>> held;
    for (int i = 0; i < 3; ++i) {
        int age = -1;
        auto buffer = swapchain->next(&age);
        if (!buffer || age != 0) return fail("initial repaint age");
        buffer->backendPin();
        held.push_back(buffer);
    }
    if (swapchain->next(nullptr)) return fail("all in-flight buffers reused");
    held[1]->backendUnpin();
    if (swapchain->next(nullptr) != held[1]) return fail("released buffer not selected");
    held[1]->backendPin();
    if (swapchain->reconfigure(SSwapchainOptions{.length = 3, .size = {8192, 8192}})) return fail("oversized allocation accepted");
    if (swapchain->currentOptions().size != Hyprutils::Math::Vector2D{3, 2}) return fail("failed reconfigure destroyed state");
    if (!swapchain->reconfigure(SSwapchainOptions{.length = 2, .size = {5, 4}})) return fail("resize failed");
    auto resized = swapchain->next(nullptr);
    if (!resized || resized->size != Hyprutils::Math::Vector2D{5, 4}) return fail("new size missing");
    for (auto& buffer : held) {
        if (std::get<0>(buffer->beginDataPtr(0))) return fail("old pending memory reused after resize");
        buffer->backendUnpin();
    }
    if (!swapchain->reconfigure(SSwapchainOptions{} ) || swapchain->next(nullptr)) return fail("clear failed");
    std::printf("SHM swapchain passed uid=%u: format, release selection, exhaustion, resize, atomic failure\n", getuid());
    return 0;
}
