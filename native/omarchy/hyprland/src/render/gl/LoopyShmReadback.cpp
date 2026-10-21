// SPDX-License-Identifier: BSD-3-Clause
#include "LoopyShmReadback.hpp"
#include <algorithm>
#include <cmath>
#include <drm_fourcc.h>

namespace {
struct PackState {
    GLint framebuffer, packBuffer, alignment, rowLength, skipRows, skipPixels, sourceReadBuffer;
    explicit PackState(GLuint source) {
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &framebuffer);
        glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &packBuffer);
        glGetIntegerv(GL_PACK_ALIGNMENT, &alignment);
        glGetIntegerv(GL_PACK_ROW_LENGTH, &rowLength);
        glGetIntegerv(GL_PACK_SKIP_ROWS, &skipRows);
        glGetIntegerv(GL_PACK_SKIP_PIXELS, &skipPixels);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, source);
        glGetIntegerv(GL_READ_BUFFER, &sourceReadBuffer);
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glPixelStorei(GL_PACK_ROW_LENGTH, 0);
        glPixelStorei(GL_PACK_SKIP_ROWS, 0);
        glPixelStorei(GL_PACK_SKIP_PIXELS, 0);
    }
    ~PackState() {
        glReadBuffer(sourceReadBuffer);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, framebuffer);
        glBindBuffer(GL_PIXEL_PACK_BUFFER, packBuffer);
        glPixelStorei(GL_PACK_ALIGNMENT, alignment);
        glPixelStorei(GL_PACK_ROW_LENGTH, rowLength);
        glPixelStorei(GL_PACK_SKIP_ROWS, skipRows);
        glPixelStorei(GL_PACK_SKIP_PIXELS, skipPixels);
    }
};
}

bool LoopyOmarchy::resolveToSHM(GLuint framebuffer, Aquamarine::IBuffer& buffer, std::vector<uint8_t>& scratch,
                               RowOrder sourceRows) {
    const auto attrs = buffer.shm();
    if ((sourceRows != RowOrder::BottomToTop && sourceRows != RowOrder::TopToBottom) ||
        !framebuffer || !buffer.good() || buffer.backendPinCount() || !attrs.success || attrs.offset != 0 ||
        (attrs.format != DRM_FORMAT_ARGB8888 && attrs.format != DRM_FORMAT_XRGB8888) ||
        !std::isfinite(attrs.size.x) || !std::isfinite(attrs.size.y) ||
        attrs.size.x < 1 || attrs.size.y < 1 || attrs.size.x > 8192 || attrs.size.y > 8192 ||
        std::trunc(attrs.size.x) != attrs.size.x || std::trunc(attrs.size.y) != attrs.size.y ||
        buffer.size != attrs.size || attrs.stride < attrs.size.x * 4)
        return false;
    const size_t width = attrs.size.x, height = attrs.size.y;
    const size_t bytes = width * height * 4;
    const size_t extent = static_cast<size_t>(attrs.stride) * height;
    if (bytes > 64 * 1024 * 1024 || extent > 64 * 1024 * 1024 || glGetError() != GL_NO_ERROR)
        return false;
    scratch.resize(bytes);
    {
        PackState state(framebuffer);
        if (glCheckFramebufferStatus(GL_READ_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
            return false;
        glReadBuffer(GL_COLOR_ATTACHMENT0);
        glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, scratch.data());
        if (glGetError() != GL_NO_ERROR)
            return false;
    }
    auto [destination, format, length] = buffer.beginDataPtr(0);
    if (!destination)
        return false;
    if (format != attrs.format || length < extent) {
        buffer.endDataPtr();
        return false;
    }
    for (size_t y = 0; y < height; ++y) {
        const size_t sourceY = sourceRows == RowOrder::TopToBottom ? y : height - y - 1;
        const auto* row = scratch.data() + sourceY * width * 4;
        auto* output = destination + y * attrs.stride;
        for (size_t x = 0; x < width; ++x) {
            output[x*4] = row[x*4+2];
            output[x*4+1] = row[x*4+1];
            output[x*4+2] = row[x*4];
            output[x*4+3] = attrs.format == DRM_FORMAT_XRGB8888 ? 255 : row[x*4+3];
        }
        std::fill(output + width*4, output + attrs.stride, 0);
    }
    buffer.endDataPtr();
    return true;
}
