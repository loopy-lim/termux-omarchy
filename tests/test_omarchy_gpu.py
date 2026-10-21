"""Actual ctypes shader ABI and Java promotion boundaries; no device mutation."""
import ctypes
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'android/assets/omarchy-bridge/gpu_probe.py'

STUB = r'''
#include <stdint.h>
#include <string.h>
static void *D=(void*)(uintptr_t)0x100000001ULL,*C=(void*)(uintptr_t)0x200000002ULL;
static void *S=(void*)(uintptr_t)0x300000003ULL,*X=(void*)(uintptr_t)0x400000004ULL;
int failure=0, cleanup=0, current=0, draw=0, deleted=0, shaders=0;
unsigned eglGetError(void){return 0x3009;}
void *eglGetDisplay(void *n){return n==0?D:0;}
unsigned eglInitialize(void *d,int *a,int *b){if(d!=D||failure==1)return 0;*a=1;*b=5;return 1;}
unsigned eglBindAPI(unsigned a){return a==0x30a0;}
unsigned eglChooseConfig(void *d,const int *a,void **c,int n,int *count){
 if(d!=D||a[0]!=0x3033||a[1]!=1||a[2]!=0x3040||a[3]!=0x40||n!=1)return 0;
 *c=C;*count=1;return 1;}
void *eglCreatePbufferSurface(void *d,void *c,const int *a){return d==D&&c==C&&a[1]==2&&a[3]==2?S:0;}
void *eglCreateContext(void *d,void *c,void *s,const int *a){return d==D&&c==C&&!s&&a[0]==0x3098&&a[1]==3?X:0;}
unsigned eglMakeCurrent(void *d,void *a,void *b,void *x){
 if(d!=D||failure==2)return 0;if(!a&&!b&&!x){current=0;cleanup|=1;return 1;}
 current=a==S&&b==S&&x==X;return current;}
unsigned eglDestroyContext(void *d,void *x){if(failure==8)return 0;if(d==D&&x==X)cleanup|=2;return 1;}
unsigned eglDestroySurface(void *d,void *s){if(d==D&&s==S)cleanup|=4;return 1;}
unsigned eglTerminate(void *d){if(d==D)cleanup|=8;return 1;}
const char *glGetString(unsigned n){
 if(!current)return 0;if(n==0x1f02)return failure==9?"OpenGL ES 2.0 fixture":"OpenGL ES 3.2 fixture";
 if(n!=0x1f01)return 0;
 return failure==3?"virgl (llvmpipe (LLVM 19))":"virgl (Adreno (TM) 830)";}
unsigned glGetError(void){return failure==7?0x502:0;}
unsigned glCreateShader(unsigned type){return type==0x8b31?1:type==0x8b30?2:0;}
void glShaderSource(unsigned s,int count,const char **text,const int *length){
 if(count==1&&text&&strstr(text[0],"#version 300 es")&&length&&length[0]>0)shaders|=1<<s;}
void glCompileShader(unsigned s){(void)s;}
void glGetShaderiv(unsigned s,unsigned n,int *v){*v=failure!=4&&(shaders&(1<<s))!=0&&n==0x8b81;}
void glDeleteShader(unsigned s){deleted|=1<<s;}
unsigned glCreateProgram(void){return 3;}
void glAttachShader(unsigned p,unsigned s){(void)p;(void)s;}
void glLinkProgram(unsigned p){(void)p;}
void glGetProgramiv(unsigned p,unsigned n,int *v){*v=p==3&&n==0x8b82&&failure!=5&&shaders==6;}
void glDeleteProgram(unsigned p){if(p==3)deleted|=8;}
void glUseProgram(unsigned p){if(p!=3)draw=-1;}
void glGenVertexArrays(int n,unsigned *a){if(n==1)*a=4;}
void glBindVertexArray(unsigned a){if(a!=4)draw=-1;}
void glDeleteVertexArrays(int n,const unsigned *a){if(n==1&&*a==4)deleted|=16;}
void glViewport(int x,int y,int w,int h){if(x||y||w!=2||h!=2)draw=-1;}
void glDisable(unsigned cap){if(cap!=0x0bd0)draw=-1;}
void glDrawArrays(unsigned mode,int start,int n){if(current&&mode==4&&!start&&n==3&&draw!=-1)draw=1;}
void glReadPixels(int x,int y,int w,int h,unsigned format,unsigned type,void *pixels){
 if(!draw||x||y||w!=2||h!=2||format!=0x1908||type!=0x1401)return;
 unsigned char *p=pixels;for(int i=0;i<4;i++){p[i*4]=51;p[i*4+1]=102;p[i*4+2]=153;p[i*4+3]=255;}
 if(failure==6)p[7]=0;
}
'''


class OmarchyGPUProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        source = Path(cls.directory.name) / 'gpu.c'
        cls.binary = source.with_suffix('.so')
        source.write_text(STUB)
        shared = '-dynamiclib' if sys.platform == 'darwin' else '-shared'
        result = subprocess.run([shutil.which('cc'), shared, '-fPIC', str(source), '-o', str(cls.binary)],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise AssertionError(result.stderr)

    def setUp(self):
        self.assertTrue(PROBE.is_file(), 'Omarchy GLES3 shader preflight missing')
        spec = importlib.util.spec_from_file_location('omarchy_gpu', PROBE)
        self.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.probe)
        self.library = ctypes.CDLL(str(self.binary))
        for name in ('failure', 'cleanup', 'current', 'draw', 'deleted', 'shaders'):
            ctypes.c_int.in_dll(self.library, name).value = 0

    def execute(self):
        return self.probe.probe(loader=lambda _: self.library)

    def test_gles3_compile_link_draw_readback_and_64bit_cleanup(self):
        result = self.execute()
        self.assertTrue(result['ready'], result)
        self.assertEqual(result['renderer'], 'virgl (Adreno (TM) 830)')
        self.assertEqual(result['rgba'], [51, 102, 153, 255])
        self.assertEqual(ctypes.c_int.in_dll(self.library, 'draw').value, 1)
        self.assertEqual(ctypes.c_int.in_dll(self.library, 'cleanup').value, 15)
        self.assertEqual(ctypes.c_int.in_dll(self.library, 'deleted').value, 30)

    def test_egl_renderer_compile_link_pixel_and_gl_failures_never_promote(self):
        for failure in range(1, 10):
            with self.subTest(failure=failure):
                for name in ('failure', 'cleanup', 'current', 'draw', 'deleted', 'shaders'):
                    ctypes.c_int.in_dll(self.library, name).value = 0
                ctypes.c_int.in_dll(self.library, 'failure').value = failure
                result = self.execute()
                self.assertFalse(result['ready'], result)
                self.assertTrue(result['reason'])
                self.assertEqual(ctypes.c_int.in_dll(self.library, 'cleanup').value,
                                 {1: 0, 2: 14, 8: 13}.get(failure, 15))

    def test_missing_socket_exits_with_one_bounded_failure_line(self):
        result = subprocess.run([sys.executable, str(PROBE), '--socket', '/run/loopy/virgl-missing.sock'],
                                capture_output=True, text=True, timeout=3,
                                env=dict(os.environ, GALLIUM_DRIVER='virpipe',
                                         VTEST_SOCKET_NAME='/run/loopy/virgl-missing.sock'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'LOOPY_OMARCHY_GPU_UNAVAILABLE_V1\n')
        self.assertLess(len(result.stderr), 512)

    def test_foreign_socket_uid_cannot_launch_gl_or_publish_ready(self):
        socket = '/run/loopy/virgl-current.sock'
        info = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o600, st_uid=os.getuid() + 1)
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', [str(PROBE), '--socket', socket]), \
                mock.patch.dict(os.environ, GALLIUM_DRIVER='virpipe', VTEST_SOCKET_NAME=socket), \
                mock.patch.object(self.probe.os, 'lstat', return_value=info), \
                mock.patch.object(self.probe, 'probe', return_value={'ready': True, 'renderer': self.probe.RENDERER}) as gl, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.probe.main(), 69)
        gl.assert_not_called()
        self.assertEqual(output.getvalue(), 'LOOPY_OMARCHY_GPU_UNAVAILABLE_V1\n')
