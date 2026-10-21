from pathlib import Path
import subprocess
root=Path(__file__).resolve().parent
import sys
s=Path(sys.argv[1]).read_text();a=s.index('static int\ntva_sync_retry');b=s.index('static bool\ntva_copy_frame_direct',a)
pre=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <assert.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#define DMA_BUF_SYNC_START 0
#define DMA_BUF_SYNC_END 4
#define DMA_BUF_SYNC_WRITE 2
#define DMA_BUF_IOCTL_SYNC 123
#define WINSYS_HANDLE_TYPE_FD 1
#define PIPE_HANDLE_USAGE_FRAMEBUFFER_WRITE 2
struct dma_buf_sync {uint64_t flags;};
struct winsys_handle {int type,handle; unsigned stride,offset;};
struct pipe_resource {unsigned format,index;};
struct pipe_screen {bool (*resource_get_handle)(struct pipe_screen*,void*,struct pipe_resource*,struct winsys_handle*,int);};
struct pipe_context {struct pipe_screen *screen;};
struct tva_codec {struct pipe_context *pipe; bool copy_profile; uint64_t profile_batch_ns,profile_batch_ok,profile_batch_fallback,profile_batch_sync_end_ns;};
static uint64_t os_time_get_nano(void) {return 0;}
static unsigned util_format_get_blocksize(unsigned f) {return f;}
static int files[2], starts,ends,retry_start,retry_end,fail_end,fail_start;
static unsigned offsets[2]={0,32};
static bool get_handle(struct pipe_screen *s,void *p,struct pipe_resource *r,struct winsys_handle *h,int flags) {h->handle=dup(files[r->index]);h->stride=8;h->offset=offsets[r->index];return true;}
static int mock_ioctl(int fd,int request,struct dma_buf_sync *s) {
 if(s->flags & DMA_BUF_SYNC_END) {ends++;if(retry_end-- > 0){errno=EAGAIN;return -1;}if(fail_end){errno=EIO;return -1;}}
 else {starts++;if(fail_start){errno=EIO;return -1;}if(retry_start-- > 0){errno=EINTR;return -1;}}
 return 0;
}
#define ioctl mock_ioctl
'''
post=r'''
int main(void) {
 char names[2][32]={"/tmp/loopy-batch-a-XXXXXX","/tmp/loopy-batch-b-XXXXXX"};
 int fd=mkstemp(names[0]), other=mkstemp(names[1]);assert(fd>=0&&other>=0);unlink(names[0]);unlink(names[1]);assert(!ftruncate(fd,64)&&!ftruncate(other,64));
 files[0]=files[1]=fd;
 struct pipe_screen screen={get_handle};struct pipe_context pipe={&screen};struct tva_codec c={.pipe=&pipe};
 struct pipe_resource yres={1,0},uvres={2,1};struct pipe_resource *res[]={&yres,&uvres};
 uint8_t y[16]={1,2,3,4,99,99,99,99,5,6,7,8},uv[8]={9,10,11,12};
 setenv("DMD_VA_BATCH_SYNC","1",1);
 assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==1);assert(starts==1&&ends==1);
 uint8_t out[64];assert(pread(fd,out,64,0)==64);assert(!memcmp(out,y,4)&&!memcmp(out+8,y+8,4)&&!memcmp(out+32,uv,4));assert(out[4]==0&&out[12]==0&&out[36]==0);
 starts=ends=0;retry_start=retry_end=2;assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==1);assert(starts==3&&ends==3);
 starts=ends=0;fail_end=1;assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==-1);assert(starts==1&&ends==1);fail_end=0;
 starts=ends=0;fail_start=1;assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==-1);assert(starts==1&&!ends);fail_start=0;
 starts=ends=0;files[1]=other;assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==0);assert(!starts&&!ends);files[1]=fd;
 offsets[1]=8;assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==0);assert(!starts&&!ends);
 offsets[1]=63;assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==0);assert(!starts&&!ends);
 offsets[1]=32;setenv("DMD_VA_BATCH_SYNC","0",1);assert(tva_copy_shared_planes(&c,res,y,uv,4,2,2,1,8)==0);assert(!starts&&!ends);
 close(fd);close(other);puts("PASS: aliased padded planes, retries, permanent START/END failures, distinct objects, overlap, bounds, opt-out");
}
'''
f=Path('/tmp/loopy-batch-helper-test.c');f.write_text(pre+s[a:b]+post)
subprocess.run(['cc','-std=gnu11','-fsanitize=address,undefined',str(f),'-o','/tmp/loopy-batch-helper-test'],check=True)
r=subprocess.run(['/tmp/loopy-batch-helper-test'],capture_output=True,text=True,check=True,timeout=10);print(r.stdout);(root/'batch-helper-test.log').write_text(r.stdout+r.stderr)
