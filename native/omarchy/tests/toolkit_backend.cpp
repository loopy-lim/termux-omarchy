// Diagnostic only: use the installed original toolkit with the compositor's environment.
#include <hyprtoolkit/core/Backend.hpp>
#include <cstdio>

int main() {
    auto backend = Hyprtoolkit::IBackend::create();
    std::fprintf(stderr, "owned-toolkit-backend-created=%s\n", backend ? "true" : "false");
    if (backend)
        backend->destroy();
    return backend ? 0 : 70;
}
