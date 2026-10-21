"""One offscreen GLES2 attempt. Called only in an expendable probe child."""
import ctypes as c


class EGLFailure(Exception):
    pass


def _bind(library, name, result, arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


def probe(loader=c.CDLL):
    """Return actual renderer/readback evidence, never presentation capability."""
    evidence = {"renderer": "", "pixelVerified": False, "reason": ""}
    display = surface = context = None
    initialized = current = False
    egl = None
    try:
        egl = loader("libEGL.so.1")
        gl = loader("libGLESv2.so.2")
        pointer, integer, boolean = c.c_void_p, c.c_int, c.c_uint
        ints = c.POINTER(integer)
        _bind(egl, "eglGetDisplay", pointer, [pointer])
        _bind(egl, "eglInitialize", boolean, [pointer, ints, ints])
        _bind(egl, "eglGetError", integer, [])
        _bind(egl, "eglBindAPI", boolean, [c.c_uint])
        _bind(egl, "eglChooseConfig", boolean,
              [pointer, ints, c.POINTER(pointer), integer, ints])
        _bind(egl, "eglCreatePbufferSurface", pointer, [pointer, pointer, ints])
        _bind(egl, "eglCreateContext", pointer, [pointer, pointer, pointer, ints])
        _bind(egl, "eglMakeCurrent", boolean, [pointer, pointer, pointer, pointer])
        _bind(egl, "eglDestroyContext", boolean, [pointer, pointer])
        _bind(egl, "eglDestroySurface", boolean, [pointer, pointer])
        _bind(egl, "eglTerminate", boolean, [pointer])
        _bind(gl, "glGetString", c.c_char_p, [c.c_uint])
        _bind(gl, "glGetError", c.c_uint, [])
        _bind(gl, "glClearColor", None, [c.c_float] * 4)
        _bind(gl, "glClear", None, [c.c_uint])
        _bind(gl, "glReadPixels", None,
              [integer, integer, integer, integer, c.c_uint, c.c_uint, pointer])

        def checked(value, operation):
            if not value:
                raise EGLFailure(f"{operation} failed (EGL error 0x{egl.eglGetError():04x})")
            return value

        display = checked(egl.eglGetDisplay(None), "eglGetDisplay")
        major, minor = integer(), integer()
        checked(egl.eglInitialize(display, c.byref(major), c.byref(minor)), "eglInitialize")
        initialized = True
        checked(egl.eglBindAPI(0x30A0), "eglBindAPI GLES2")
        attributes = (integer * 13)(0x3033, 1, 0x3040, 4, 0x3024, 8,
                                    0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
        config, count = pointer(), integer()
        checked(egl.eglChooseConfig(display, attributes, c.byref(config), 1,
                                    c.byref(count)), "eglChooseConfig")
        if count.value != 1 or not config.value:
            raise EGLFailure("no RGBA8 GLES2 pbuffer config")
        dimensions = (integer * 5)(0x3057, 1, 0x3056, 1, 0x3038)
        surface = checked(egl.eglCreatePbufferSurface(display, config, dimensions),
                          "eglCreatePbufferSurface")
        context_attributes = (integer * 3)(0x3098, 2, 0x3038)
        context = checked(egl.eglCreateContext(display, config, None, context_attributes),
                          "eglCreateContext")
        checked(egl.eglMakeCurrent(display, surface, surface, context), "eglMakeCurrent")
        current = True
        renderer = gl.glGetString(0x1F01)
        if not renderer:
            raise EGLFailure("GL_RENDERER is empty")
        evidence["renderer"] = renderer.decode("utf-8", errors="replace")[:512]
        pixels = (c.c_ubyte * 4)()
        gl.glClearColor(.2, .4, .6, 1.0)
        gl.glClear(0x4000)
        gl.glReadPixels(0, 0, 1, 1, 0x1908, 0x1401, pixels)
        error = gl.glGetError()
        if error:
            raise EGLFailure(f"GLES2 readback failed (GL error 0x{error:04x})")
        if list(pixels) != [51, 102, 153, 255]:
            raise EGLFailure("GLES2 pixel readback did not match RGBA [51,102,153,255]")
        evidence["pixelVerified"] = True
        evidence["reason"] = "GLES2 offscreen pixels verified; desktop presentation not tested"
    except (OSError, AttributeError, EGLFailure, ValueError) as error:
        evidence["reason"] = str(error)[:512]
    finally:
        # Every call remains on this child thread. Partial creation also releases owners.
        if egl is not None:
            actions = []
            if current:
                actions.append(("eglMakeCurrent", (display, None, None, None)))
            if context:
                actions.append(("eglDestroyContext", (display, context)))
            if surface:
                actions.append(("eglDestroySurface", (display, surface)))
            if initialized:
                actions.append(("eglTerminate", (display,)))
            for name, arguments in actions:
                try:
                    getattr(egl, name)(*arguments)
                except (AttributeError, OSError, ValueError):
                    pass
    return evidence
