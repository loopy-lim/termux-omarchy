// SPDX-License-Identifier: BSD-3-Clause
// Real GLES3 shader/FBO/blend/readback using owned pixels and actual AQ memory.
#include "../hyprland/src/render/gl/LoopyShmReadback.hpp"
#include <aquamarine/backend/Backend.hpp>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <cmath>
#include <cstdio>
#include <unistd.h>

static int fail(const char* reason) { std::fprintf(stderr, "GLES3 SHM: %s\n", reason); return 1; }
static GLuint shader(GLenum type, const char* source) {
    auto handle = glCreateShader(type);
    glShaderSource(handle, 1, &source, nullptr);
    glCompileShader(handle);
    GLint compiled = 0;
    glGetShaderiv(handle, GL_COMPILE_STATUS, &compiled);
    if (!compiled) { glDeleteShader(handle); return 0; }
    return handle;
}

int main() {
    if (getuid() == 0) return fail("ordinary user required");
    auto display = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, nullptr, nullptr);
    EGLint major, minor;
    if (display == EGL_NO_DISPLAY || !eglInitialize(display, &major, &minor) || !eglBindAPI(EGL_OPENGL_ES_API)) return fail("surfaceless EGL unavailable");
    EGLint attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
    auto context = eglCreateContext(display, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, attrs);
    if (context == EGL_NO_CONTEXT || !eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, context)) return fail("GLES3 context unavailable");
    const char* vertex = "#version 300 es\nvoid main(){vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);}";
    const char* fragment = "#version 300 es\nprecision highp float;out vec4 color;void main(){color=gl_FragCoord.y<1.0?vec4(.5,0,.25,.5):vec4(0,.75,.125,1);}";
    auto vs = shader(GL_VERTEX_SHADER, vertex), fs = shader(GL_FRAGMENT_SHADER, fragment);
    if (!vs || !fs) return fail("shader compilation");
    auto program = glCreateProgram();
    glAttachShader(program, vs); glAttachShader(program, fs); glLinkProgram(program);
    GLint linked = 0; glGetProgramiv(program, GL_LINK_STATUS, &linked);
    if (!linked) return fail("shader linkage");
    GLuint fb, texture;
    glGenFramebuffers(1, &fb); glBindFramebuffer(GL_FRAMEBUFFER, fb);
    glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
    glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, 3, 2);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return fail("FBO incomplete");
    glViewport(0, 0, 3, 2); glClearColor(0, 0, 1, 1); glClear(GL_COLOR_BUFFER_BIT);
    glEnable(GL_BLEND); glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
    glUseProgram(program); glDrawArrays(GL_TRIANGLES, 0, 3);
    setenv("AQ_SHM_ONLY", "1", 1);
    Aquamarine::SBackendImplementationOptions implementation;
    implementation.backendType = Aquamarine::AQ_BACKEND_HEADLESS;
    implementation.backendRequestMode = Aquamarine::AQ_BACKEND_REQUEST_MANDATORY;
    auto backend = Aquamarine::CBackend::create({implementation}, Aquamarine::SBackendOptions{});
    if (!backend || !backend->start()) return fail("SHM allocator unavailable");
    auto buffer = backend->primaryAllocator->acquire(Aquamarine::SAllocatorBufferParams{.size = {3, 2}}, nullptr);
    GLuint pack;
    glGenBuffers(1, &pack); glBindBuffer(GL_PIXEL_PACK_BUFFER, pack); glBufferData(GL_PIXEL_PACK_BUFFER, 128, nullptr, GL_STREAM_READ);
    glPixelStorei(GL_PACK_ALIGNMENT, 8); glPixelStorei(GL_PACK_ROW_LENGTH, 7); glPixelStorei(GL_PACK_SKIP_ROWS, 1); glPixelStorei(GL_PACK_SKIP_PIXELS, 1);
    std::vector<uint8_t> scratch;
    if (!LoopyOmarchy::resolveToSHM(fb, *buffer, scratch)) return fail("FBO readback failed");
    for (auto [name, expected] : {std::pair{GL_PIXEL_PACK_BUFFER_BINDING, static_cast<GLint>(pack)},
             {GL_PACK_ALIGNMENT, 8}, {GL_PACK_ROW_LENGTH, 7}, {GL_PACK_SKIP_ROWS, 1}, {GL_PACK_SKIP_PIXELS, 1}}) {
        GLint value = -1; glGetIntegerv(name, &value);
        if (value != expected) return fail("caller pack state corrupted");
    }
    auto [pixels, format, length] = buffer->beginDataPtr(0);
    if (!pixels || format != DRM_FORMAT_ARGB8888 || length != 128) return fail("SHM mapping/stride");
    const int expected[2][4] = {{32, 191, 0, 255}, {191, 0, 128, 255}};
    for (int y = 0; y < 2; ++y) for (int x = 0; x < 3; ++x) for (int c = 0; c < 4; ++c)
        if (std::abs(static_cast<int>(pixels[y*64+x*4+c])-expected[y][c]) > 1) return fail("orientation, channel or alpha mismatch");
    buffer->endDataPtr();
    // Hyprland's final output projection puts the desktop's top row at GL y=0.
    // Unlike a conventional bottom-origin FBO, this output must not be flipped
    // again before Wayland interprets SHM row zero as the top of the desktop.
    if (!LoopyOmarchy::resolveToSHM(fb, *buffer, scratch, LoopyOmarchy::RowOrder::TopToBottom))
        return fail("Hyprland output row order is unsupported");
    auto [nativeRows, nativeFormat, nativeLength] = buffer->beginDataPtr(0);
    if (!nativeRows || nativeFormat != DRM_FORMAT_ARGB8888 || nativeLength != 128)
        return fail("Hyprland output mapping");
    for (int y = 0; y < 2; ++y) for (int x = 0; x < 3; ++x) for (int c = 0; c < 4; ++c)
        if (std::abs(static_cast<int>(nativeRows[y*64+x*4+c])-expected[1-y][c]) > 1)
            return fail("Hyprland output was vertically flipped");
    buffer->endDataPtr(); buffer->backendPin();
    if (LoopyOmarchy::resolveToSHM(fb, *buffer, scratch)) return fail("in-flight buffer overwritten");
    buffer->backendUnpin();
    if (LoopyOmarchy::resolveToSHM(0, *buffer, scratch)) return fail("undefined framebuffer falsely accepted");
    if (!LoopyOmarchy::resolveToSHM(fb, *buffer, scratch)) return fail("recovery/reuse failed");
    glClearColor(0, 0, 0, 0); glClear(GL_COLOR_BUFFER_BIT); glDrawArrays(GL_TRIANGLES, 0, 3);
    if (!LoopyOmarchy::resolveToSHM(fb, *buffer, scratch)) return fail("transparent ARGB readback failed");
    auto [alphaPixels, alphaFormat, alphaLength] = buffer->beginDataPtr(0);
    if (!alphaPixels || std::abs(static_cast<int>(alphaPixels[67])-128) > 1) return fail("ARGB alpha lost");
    buffer->endDataPtr();
    auto opaque = backend->primaryAllocator->acquire(Aquamarine::SAllocatorBufferParams{.size = {3, 2}, .format = DRM_FORMAT_XRGB8888}, nullptr);
    if (!opaque || !LoopyOmarchy::resolveToSHM(fb, *opaque, scratch)) return fail("XRGB readback failed");
    auto [opaquePixels, opaqueFormat, opaqueLength] = opaque->beginDataPtr(0);
    if (!opaquePixels || opaqueFormat != DRM_FORMAT_XRGB8888 || opaquePixels[67] != 255 ||
        std::abs(static_cast<int>(opaquePixels[66])-128) > 1) return fail("XRGB opacity/channel mismatch");
    opaque->endDataPtr();
    std::printf("GLES3 SHM passed uid=%u renderer=%s: shader, premultiplied alpha, both FBO row orders, BGRA, stride, pack state, release reuse\n", getuid(), glGetString(GL_RENDERER));
    glBindBuffer(GL_PIXEL_PACK_BUFFER, 0); glDeleteBuffers(1, &pack);
    glDeleteProgram(program); glDeleteShader(vs); glDeleteShader(fs);
    glDeleteTextures(1, &texture); glDeleteFramebuffers(1, &fb);
    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroyContext(display, context); eglTerminate(display);
    return 0;
}
