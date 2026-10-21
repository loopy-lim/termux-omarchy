// SPDX-License-Identifier: BSD-3-Clause
// Only owned, fixed red pixels; no device or personal application capture.
#include <aquamarine/backend/Backend.hpp>
#include <aquamarine/output/Output.hpp>
#include <chrono>
#include <cstdio>
#include <poll.h>
#include <unistd.h>

using namespace Aquamarine;
using namespace Hyprutils::Memory;
static int fail(const char* reason) { std::fprintf(stderr, "Wayland SHM: %s\n", reason); return 1; }

int main() {
    if (getuid() == 0) return fail("ordinary user required");
    setenv("AQ_SHM_ONLY", "1", 1);
    SBackendImplementationOptions implementation;
    implementation.backendType = AQ_BACKEND_WAYLAND;
    implementation.backendRequestMode = AQ_BACKEND_REQUEST_MANDATORY;
    SBackendOptions options;
    options.logFunction = [](eBackendLogLevel level, std::string text) {
        if (level >= AQ_LOG_ERROR) std::fprintf(stderr, "%s\n", text.c_str());
    };
    auto backend = CBackend::create({implementation}, options);
    if (!backend) return fail("backend creation failed");
    CSharedPointer<IOutput> output;
    CSharedPointer<IBuffer> buffer;
    bool configured = false;
    int releases = 0, frames = 0;
    const char* failure = nullptr;
    std::function<const char*()> submit;
    Hyprutils::Signal::CHyprSignalListener state, release, frame;
    auto newOutput = backend->events.newOutput.listen([&](CSharedPointer<IOutput> created) {
        output = created;
        state = output->events.state.listen([&](const IOutput::SStateEvent&) {
            configured = true;
            failure = submit(); // mimic a real compositor's synchronous configure handler
        });
    });
    if (!backend->start()) return fail("SHM-only parent rejected");
    if (backend->drmFD() != -1) return fail("unexpected DRM dependency");
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
    const auto dispatch = [&]() {
        auto sources = backend->getPollFDs();
        std::vector<pollfd> descriptors;
        for (const auto& source : sources) descriptors.push_back({source->fd, POLLIN, 0});
        if (poll(descriptors.data(), descriptors.size(), 50) < 0) return false;
        for (size_t i = 0; i < sources.size(); ++i) {
            if (descriptors[i].revents & (POLLERR | POLLHUP | POLLNVAL)) return false;
            if (descriptors[i].revents & POLLIN) sources[i]->onSignal();
        }
        return true;
    };
    submit = [&]() -> const char* {
    if (!output || !output->swapchain) return "no output";
    if (output->modes.empty() || !output->modes[0]->preferred || output->modes[0]->refreshRate != 60000)
        return "parent mode not announced";
    if (!output->swapchain->reconfigure(SSwapchainOptions{.length = 3, .size = {640, 360}, .scanout = true})) return "nested output allocation failed";
    if (output->swapchain->currentOptions().format != DRM_FORMAT_ARGB8888) return "SHM default format lost";
    auto mode = makeShared<SOutputMode>(SOutputMode{.pixelSize = {640, 360}, .refreshRate = 60000});
    output->state->setCustomMode(mode);
    output->state->setEnabled(true);
    output->state->setFormat(DRM_FORMAT_ARGB8888);
    buffer = output->swapchain->next(nullptr);
    if (!buffer) return "no writable buffer";
    auto attrs = buffer->shm();
    auto [pixels, format, length] = buffer->beginDataPtr(0);
    if (!pixels || format != DRM_FORMAT_ARGB8888 || length < static_cast<size_t>(attrs.stride * 360)) return "invalid pixels";
    for (size_t i = 0; i < length; i += 4) { pixels[i] = 0; pixels[i+1] = 0; pixels[i+2] = 255; pixels[i+3] = 255; }
    buffer->endDataPtr();
    release = buffer->events.backendRelease.listen([&] { ++releases; });
    frame = output->events.present.listen([&](const IOutput::SPresentEvent& event) { if (event.presented) ++frames; });
    output->state->setBuffer(buffer);
    if (!output->commit()) return "commit rejected";
    if (!buffer->backendPinCount() || std::get<0>(buffer->beginDataPtr(0))) return "in-flight SHM is writable";
    output->state->setBuffer(buffer);
    if (output->commit()) return "unreleased buffer submitted twice";
    return nullptr;
    };
    while (!configured && std::chrono::steady_clock::now() < deadline) if (!dispatch()) return fail("configure dispatch failed");
    if (!configured) return fail("configure not delivered");
    if (failure) return fail(failure);
    while ((releases == 0 || frames == 0) && std::chrono::steady_clock::now() < deadline)
        if (!dispatch()) return fail("frame dispatch failed");
    if (releases != 1 || frames < 1 || buffer->backendPinCount()) return fail("release/frame not acknowledged");
    if (!std::get<0>(buffer->beginDataPtr(0))) return fail("released SHM cannot be reused");
    buffer->endDataPtr();
    if (!output->setCursor(buffer, {0, 0})) return fail("SHM cursor rejected");
    if (!std::get<0>(buffer->beginDataPtr(0))) return fail("cursor copy leaked SHM access");
    buffer->endDataPtr();
    if (!output->setCursor(buffer, {0, 0})) return fail("SHM cursor reuse rejected");
    buffer->backendPin();
    if (output->setCursor(buffer, {0, 0})) return fail("parent-owned cursor source accepted");
    buffer->backendUnpin();
    if (!std::get<0>(buffer->beginDataPtr(0))) return fail("cursor source access unavailable");
    if (output->setCursor(buffer, {0, 0})) return fail("already-mapped cursor source accepted");
    if (std::get<0>(buffer->beginDataPtr(0))) return fail("failed cursor copy closed caller access");
    buffer->endDataPtr();
    if (!output->setCursor(nullptr, {0, 0})) return fail("cursor hide rejected");
    std::printf("Wayland SHM passed uid=%u: commit, frame, release, reuse, cursor reuse/hide; presents=%d releases=%d\n", getuid(), frames, releases);
    return 0;
}
