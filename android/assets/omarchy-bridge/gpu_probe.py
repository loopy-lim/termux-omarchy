"""Current-session GLES3 draw/readback preflight; presentation remains separate."""
import argparse
import ctypes as c
import os
import re
import stat
import sys

RENDERER = 'virgl (Adreno (TM) 830)'
READY = 'LOOPY_OMARCHY_GPU_READY_V1'
UNAVAILABLE = 'LOOPY_OMARCHY_GPU_UNAVAILABLE_V1'
SOCKET = re.compile(r'/run/loopy/virgl-[A-Za-z0-9-]{1,64}\.sock\Z')
RGBA = [51, 102, 153, 255]
VERTEX = b'''#version 300 es
const vec2 positions[3] = vec2[3](vec2(-1.0,-1.0),vec2(3.0,-1.0),vec2(-1.0,3.0));
void main() { gl_Position = vec4(positions[gl_VertexID],0.0,1.0); }
'''
FRAGMENT = b'''#version 300 es
precision highp float;
layout(location=0) out vec4 color;
void main() { color = vec4(51.0,102.0,153.0,255.0) / 255.0; }
'''


class GPUFailure(Exception):
    pass


def bind(library, name, result, arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


def probe(loader=c.CDLL):
    """Run real shader compilation and rasterization on this guest context."""
    result = {'ready': False, 'renderer': '', 'rgba': [], 'reason': ''}
    egl = gl = None
    display = surface = context = None
    initialized = current = False
    shaders = []
    program = 0
    vertex_array = c.c_uint()
    try:
        egl, gl = loader('libEGL.so.1'), loader('libGLESv2.so.2')
        pointer, integer, unsigned = c.c_void_p, c.c_int, c.c_uint
        ints = c.POINTER(integer)
        for name, returns, arguments in (
            ('eglGetDisplay', pointer, [pointer]),
            ('eglInitialize', unsigned, [pointer, ints, ints]),
            ('eglGetError', integer, []),
            ('eglBindAPI', unsigned, [unsigned]),
            ('eglChooseConfig', unsigned, [pointer, ints, c.POINTER(pointer), integer, ints]),
            ('eglCreatePbufferSurface', pointer, [pointer, pointer, ints]),
            ('eglCreateContext', pointer, [pointer, pointer, pointer, ints]),
            ('eglMakeCurrent', unsigned, [pointer, pointer, pointer, pointer]),
            ('eglDestroyContext', unsigned, [pointer, pointer]),
            ('eglDestroySurface', unsigned, [pointer, pointer]),
            ('eglTerminate', unsigned, [pointer]),
        ):
            bind(egl, name, returns, arguments)
        for name, returns, arguments in (
            ('glGetString', c.c_char_p, [unsigned]),
            ('glGetError', unsigned, []),
            ('glCreateShader', unsigned, [unsigned]),
            ('glShaderSource', None, [unsigned, integer, c.POINTER(c.c_char_p), ints]),
            ('glCompileShader', None, [unsigned]),
            ('glGetShaderiv', None, [unsigned, unsigned, ints]),
            ('glDeleteShader', None, [unsigned]),
            ('glCreateProgram', unsigned, []),
            ('glAttachShader', None, [unsigned, unsigned]),
            ('glLinkProgram', None, [unsigned]),
            ('glGetProgramiv', None, [unsigned, unsigned, ints]),
            ('glDeleteProgram', None, [unsigned]),
            ('glUseProgram', None, [unsigned]),
            ('glGenVertexArrays', None, [integer, c.POINTER(unsigned)]),
            ('glBindVertexArray', None, [unsigned]),
            ('glDeleteVertexArrays', None, [integer, c.POINTER(unsigned)]),
            ('glViewport', None, [integer] * 4),
            ('glDisable', None, [unsigned]),
            ('glDrawArrays', None, [unsigned, integer, integer]),
            ('glReadPixels', None, [integer, integer, integer, integer, unsigned, unsigned, pointer]),
        ):
            bind(gl, name, returns, arguments)

        def checked(value, operation):
            if not value:
                raise GPUFailure(f'{operation} failed: EGL 0x{egl.eglGetError():04x}')
            return value

        display = checked(egl.eglGetDisplay(None), 'eglGetDisplay')
        major, minor = integer(), integer()
        checked(egl.eglInitialize(display, c.byref(major), c.byref(minor)), 'eglInitialize')
        initialized = True
        checked(egl.eglBindAPI(0x30A0), 'eglBindAPI GLES')
        attributes = (integer * 13)(0x3033, 1, 0x3040, 0x40, 0x3024, 8,
                                   0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
        config, count = pointer(), integer()
        checked(egl.eglChooseConfig(display, attributes, c.byref(config), 1, c.byref(count)),
                'eglChooseConfig GLES3')
        if count.value != 1 or not config.value:
            raise GPUFailure('RGBA8 GLES3 pbuffer config unavailable')
        dimensions = (integer * 5)(0x3057, 2, 0x3056, 2, 0x3038)
        surface = checked(egl.eglCreatePbufferSurface(display, config, dimensions), 'eglCreatePbufferSurface')
        context_attributes = (integer * 3)(0x3098, 3, 0x3038)
        context = checked(egl.eglCreateContext(display, config, None, context_attributes), 'eglCreateContext GLES3')
        checked(egl.eglMakeCurrent(display, surface, surface, context), 'eglMakeCurrent')
        current = True
        renderer = gl.glGetString(0x1F01)
        version = gl.glGetString(0x1F02)
        result['renderer'] = renderer.decode('utf-8', errors='replace')[:256] if renderer else ''
        if result['renderer'] != RENDERER:
            raise GPUFailure('Actual guest renderer does not match the verified Adreno 830 route')
        if not version or not version.startswith(b'OpenGL ES 3.'):
            raise GPUFailure('Actual GLES3 context unavailable')

        for kind, source in ((0x8B31, VERTEX), (0x8B30, FRAGMENT)):
            shader = gl.glCreateShader(kind)
            if not shader:
                raise GPUFailure('Shader creation failed')
            shaders.append(shader)
            source_pointer, length = c.c_char_p(source), integer(len(source))
            gl.glShaderSource(shader, 1, c.byref(source_pointer), c.byref(length))
            gl.glCompileShader(shader)
            compiled = integer()
            gl.glGetShaderiv(shader, 0x8B81, c.byref(compiled))
            if not compiled.value:
                raise GPUFailure('GLES3 shader compilation failed')
        program = gl.glCreateProgram()
        if not program:
            raise GPUFailure('Program creation failed')
        for shader in shaders:
            gl.glAttachShader(program, shader)
        gl.glLinkProgram(program)
        linked = integer()
        gl.glGetProgramiv(program, 0x8B82, c.byref(linked))
        if not linked.value:
            raise GPUFailure('GLES3 shader linkage failed')
        gl.glGenVertexArrays(1, c.byref(vertex_array))
        if not vertex_array.value:
            raise GPUFailure('GLES3 vertex array unavailable')
        gl.glBindVertexArray(vertex_array.value)
        gl.glUseProgram(program)
        gl.glDisable(0x0BD0)  # Disable dithering for exact RGBA8 evidence.
        gl.glViewport(0, 0, 2, 2)
        gl.glDrawArrays(0x0004, 0, 3)
        pixels = (c.c_ubyte * 16)()
        gl.glReadPixels(0, 0, 2, 2, 0x1908, 0x1401, pixels)
        error = gl.glGetError()
        if error:
            raise GPUFailure(f'GLES3 draw/readback failed: GL 0x{error:04x}')
        if list(pixels) != RGBA * 4:
            raise GPUFailure('GLES3 shader pixel readback mismatch')
        result.update(ready=True, rgba=RGBA.copy())
    except (OSError, AttributeError, GPUFailure, ValueError) as failure:
        result['reason'] = str(failure)[:256]
    finally:
        actions = []
        if gl is not None and current:
            if vertex_array.value:
                actions.append((gl, 'glDeleteVertexArrays', (1, c.byref(vertex_array))))
            if program:
                actions.append((gl, 'glDeleteProgram', (program,)))
            actions.extend((gl, 'glDeleteShader', (shader,)) for shader in shaders)
        if egl is not None:
            if current:
                actions.append((egl, 'eglMakeCurrent', (display, None, None, None)))
            if context:
                actions.append((egl, 'eglDestroyContext', (display, context)))
            if surface:
                actions.append((egl, 'eglDestroySurface', (display, surface)))
            if initialized:
                actions.append((egl, 'eglTerminate', (display,)))
        for library, name, arguments in actions:
            try:
                returned = getattr(library, name)(*arguments)
                if name.startswith('egl') and not returned:
                    raise GPUFailure('EGL cleanup failed')
            except (AttributeError, OSError, ValueError, GPUFailure) as failure:
                result.update(ready=False, reason=str(failure)[:256])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', required=True)
    arguments = parser.parse_args()
    try:
        socket = arguments.socket
        if not SOCKET.fullmatch(socket) or os.environ.get('VTEST_SOCKET_NAME') != socket \
                or os.environ.get('GALLIUM_DRIVER') != 'virpipe':
            raise GPUFailure('Current-session VirGL socket/environment required')
        info = os.lstat(socket)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise GPUFailure('Current-session VirGL socket unavailable')
        result = probe()
        if not result['ready']:
            raise GPUFailure(result['reason'])
        print(f'{READY}\t{socket}\t{result["renderer"]}\t51,102,153,255', flush=True)
        return 0
    except (OSError, GPUFailure) as failure:
        print(UNAVAILABLE, flush=True)
        print(str(failure)[:256], file=sys.stderr)
        return 69


if __name__ == '__main__':
    sys.exit(main())
