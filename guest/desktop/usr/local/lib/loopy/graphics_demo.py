#!/usr/bin/python3
"""Visible GTK GL check; context failure leaves a usable Cairo diagnostic window."""
import ctypes as C
import json
import os
from pathlib import Path
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from graphics_session import write_report

PROOF = Path('/tmp/loopy-gl-window.json')


def main():
    window = Gtk.Window(title='Loopy OpenGL compatibility check')
    window.set_default_size(620, 420)
    window.connect('destroy', Gtk.main_quit)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    window.add(box)
    title = Gtk.Label(label='OpenGL 검사 중… · 창을 닫으면 데스크톱으로 돌아갑니다.')
    box.pack_start(title, False, False, 8)
    area = Gtk.GLArea()
    area.set_use_es(True)
    area.set_required_version(2, 0)
    area.set_has_alpha(False)
    box.pack_start(area, True, True, 0)
    finished = False
    failed = False

    def record(data):
        data.update(uid=os.getuid(), token=os.environ.get('LOOPY_SESSION', ''),
                    provider=os.environ.get('LOOPY_GL_PROVIDER', 'unknown'))
        try: write_report(PROOF, data)
        except (OSError, ValueError) as error: print(str(error), file=sys.stderr)

    def fallback(reason):
        nonlocal finished, failed
        if failed: return False
        failed = True
        finished = True
        record(dict(pixelVerified=False, selected='cairo', reason=str(reason)[:256]))
        box.remove(area)
        message = Gtk.Label(label='OpenGL 창을 만들지 못했습니다. 기본 화면 표시로 전환했습니다.\n'
                           'GPU 대체 방법에서 다른 경로의 조건을 확인하세요.\n' + str(reason)[:200])
        message.set_line_wrap(True)
        box.pack_start(message, True, True, 12)
        title.set_text('Cairo 대체 경로 · Linux 세션은 유지됩니다.')
        box.show_all()
        return False

    def realized(widget):
        widget.make_current()
        error = widget.get_error()
        if error: GLib.idle_add(fallback, error.message)

    def render(widget, context):
        nonlocal finished
        if failed: return True
        try:
            gl = C.CDLL('libGLESv2.so.2')
            gl.glClearColor.argtypes = [C.c_float] * 4
            gl.glClear.argtypes = [C.c_uint]
            gl.glReadPixels.argtypes = [C.c_int] * 4 + [C.c_uint, C.c_uint, C.c_void_p]
            gl.glGetString.argtypes = [C.c_uint]; gl.glGetString.restype = C.c_char_p
            gl.glGetError.restype = C.c_uint
            gl.glClearColor(.2, .4, .6, 1)
            gl.glClear(0x4000)
            pixel = (C.c_ubyte * 4)()
            gl.glReadPixels(0, 0, 1, 1, 0x1908, 0x1401, pixel)
            renderer = (gl.glGetString(0x1F01) or b'').decode(errors='replace')
            if gl.glGetError() or list(pixel) != [51, 102, 153, 255]:
                raise ValueError('GL readback did not match the test color')
            if not finished:
                record(dict(pixelVerified=True, selected='opengl', renderer=renderer, rgba=list(pixel)))
                title.set_text('OpenGL 픽셀 검사 통과 · ' + renderer[:100])
            finished = True
        except (OSError, ValueError) as error:
            GLib.idle_add(fallback, error)
        return True

    area.connect('realize', realized)
    area.connect('render', render)
    window.show_all()
    Gtk.main()


if __name__ == '__main__': main()
