// SPDX-License-Identifier: BSD-3-Clause
#pragma once
#include <aquamarine/buffer/Buffer.hpp>
#include <GLES3/gl3.h>
#include <vector>

namespace LoopyOmarchy {
enum class RowOrder { BottomToTop, TopToBottom };
// Resolve a rendered RGBA8 FBO into top-down Wayland ARGB/XRGB memory.
// Returns false without writing pixels on unsupported, pinned or failed inputs.
// Hyprland's final output projection already places the desktop top at GL y=0.
bool resolveToSHM(GLuint framebuffer, Aquamarine::IBuffer& buffer, std::vector<uint8_t>& scratch,
                  RowOrder sourceRows = RowOrder::BottomToTop);
}
