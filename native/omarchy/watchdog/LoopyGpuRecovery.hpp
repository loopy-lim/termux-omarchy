#pragma once

#include <cstdlib>
#include <string>
#include <string_view>

namespace LoopyOmarchy {
// Apply only to the virpipe route belonging to this prepared desktop session.
class CGpuRecovery {
  public:
    enum class Action { UPSTREAM, SOFTWARE_RETRY, FAILED };

    CGpuRecovery() : m_ownedGpuRoute(ownedGpuRoute()) { }

    Action unexpectedExit() {
        if (!m_ownedGpuRoute)
            return Action::UPSTREAM;
        if (m_softwareAttempted)
            return Action::FAILED;
        m_softwareAttempted = true;

        if (unsetenv("GALLIUM_DRIVER") != 0 || unsetenv("VTEST_SOCKET_NAME") != 0 || unsetenv("EGL_PLATFORM") != 0 ||
            setenv("LIBGL_ALWAYS_SOFTWARE", "1", 1) != 0 || setenv("QT_QUICK_BACKEND", "software", 1) != 0)
            return Action::FAILED;
        return Action::SOFTWARE_RETRY;
    }

  private:
    static bool ownedGpuRoute() {
        const char* driver = std::getenv("GALLIUM_DRIVER");
        const char* socket = std::getenv("VTEST_SOCKET_NAME");
        const char* token = std::getenv("LOOPY_SESSION");
        if (!driver || std::string_view(driver) != "virpipe" || !socket || !token)
            return false;
        const std::string_view session(token);
        if (session.empty() || session.size() > 64)
            return false;
        for (const char c : session)
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-'))
                return false;
        return std::string_view(socket) == "/run/loopy/virgl-" + std::string(session) + ".sock";
    }

    const bool m_ownedGpuRoute;
    bool       m_softwareAttempted = false;
};
}
