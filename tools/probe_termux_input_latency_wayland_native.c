/* Bionic Wayland SHM fixture. frame.done is a callback, never scan-out proof. */
#define _GNU_SOURCE
#include <wayland-client.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/memfd.h>
#include <poll.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include "probe_termux_input_latency_identity.h"
#define WIDTH 640
#define HEIGHT 420
#define LIMIT 2048
extern const struct wl_interface xdg_wm_base_interface, xdg_surface_interface, xdg_toplevel_interface;
#define REQ(o,n,i,...) wl_proxy_marshal_flags((struct wl_proxy *)(o),n,i,1,0,##__VA_ARGS__)
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct wl_surface *surface;
static struct wl_proxy *base, *xdg, *top;
static struct wl_pointer *pointer;
static struct wl_keyboard *keyboard;
static struct wl_callback *frame;
static struct wl_buffer *buffers[2];
static uint32_t *pixels;
static unsigned sequence, pending[LIMIT], pending_count, painting[LIMIT], painting_count;
static int free_buffer[2] = {1,1}, configured, ready, failed, key_focus, pointer_focus;
static volatile sig_atomic_t stopping;
static pid_t server_pid;
static uint64_t server_birth, own_birth;
static const char *nonce, *session;
static void stop_signal(int sig) { (void)sig; stopping = 1; }
static int peer(void) { return owned_peer(wl_display_get_fd(display),server_pid,server_birth) && birth(getpid()) == own_birth; }
static void note(const char *kind, uint32_t source) {
    uint64_t arrival = now_ns();
    if (!ready || stopping || sequence == LIMIT) return;
    if (!peer()) { failed = 1; return; }
    pending[pending_count++] = ++sequence;
    printf("{\"type\":\"EVENT\",\"id\":%u,\"kind\":\"%s\",\"arrival_ns\":%"PRIu64",\"source_ms\":%u}\n",sequence,kind,arrival,source);
}
static void frame_done(void *data, struct wl_callback *object, uint32_t stamp) {
    (void)data; (void)stamp; uint64_t complete = now_ns();
    wl_callback_destroy(object); frame = NULL;
    if (!peer()) { failed = 1; return; }
    if (!ready) {
        printf("{\"type\":\"READY\",\"schema\":1,\"nonce\":\"%s\",\"session\":\"%s\",\"uid\":%u,\"pid\":%d,\"birth\":%"PRIu64",\"sid\":%d,\"backend\":\"wayland-frame-callback\",\"width\":640,\"height\":420,\"window\":null}\n",nonce,session,getuid(),getpid(),own_birth,getsid(0));
        ready = 1;
    }
    if (painting_count) {
        printf("{\"type\":\"PAINT\",\"ids\":[");
        for (unsigned i=0;i<painting_count;i++) printf("%s%u",i?",":"",painting[i]);
        printf("],\"complete_ns\":%"PRIu64"}\n",complete); painting_count = 0;
    }
}
static const struct wl_callback_listener frame_listener = {.done=frame_done};
static void released(void *data, struct wl_buffer *object) { (void)object; free_buffer[(uintptr_t)data]=1; }
static const struct wl_buffer_listener buffer_listener = {.release=released};
static void draw(void) {
    if (!configured || frame || (ready && !pending_count)) return;
    int index = free_buffer[0] ? 0 : free_buffer[1] ? 1 : -1; if (index < 0) return;
    uint32_t *out = pixels + index*WIDTH*HEIGHT;
    for (int y=0;y<HEIGHT;y++) for (int x=0;x<WIDTH;x++) out[y*WIDTH+x] =
        x>=240 && x<400 && y>=130 && y<290 ? 0xffe8edf2 : sequence&1 ? 0xff31554a : 0xff24344d;
    memcpy(painting,pending,pending_count*sizeof(*pending)); painting_count=pending_count; pending_count=0;
    free_buffer[index]=0; wl_surface_attach(surface,buffers[index],0,0);
    wl_surface_damage(surface,0,0,WIDTH,HEIGHT); frame=wl_surface_frame(surface);
    if (!frame || wl_callback_add_listener(frame,&frame_listener,NULL)) { failed=1; return; }
    wl_surface_commit(surface);
}
static void keymap(void *d, struct wl_keyboard *o, uint32_t f, int32_t fd, uint32_t s) { (void)d;(void)o;(void)f;(void)s;close(fd); }
static void key_enter(void *d,struct wl_keyboard *o,uint32_t s,struct wl_surface *w,struct wl_array *a) { (void)d;(void)o;(void)s;(void)a;key_focus=w==surface; }
static void key_leave(void *d,struct wl_keyboard *o,uint32_t s,struct wl_surface *w) { (void)d;(void)o;(void)s;(void)w;key_focus=0; }
static void key(void *d,struct wl_keyboard *o,uint32_t s,uint32_t t,uint32_t k,uint32_t state) { (void)d;(void)o;(void)s;(void)k;if(key_focus)note(state?"key_down":"key_up",t); }
static void modifiers(void *d,struct wl_keyboard *o,uint32_t s,uint32_t a,uint32_t b,uint32_t c,uint32_t g) { (void)d;(void)o;(void)s;(void)a;(void)b;(void)c;(void)g; }
static const struct wl_keyboard_listener key_listener = {.keymap=keymap,.enter=key_enter,.leave=key_leave,.key=key,.modifiers=modifiers};
static void ptr_enter(void *d,struct wl_pointer *o,uint32_t s,struct wl_surface *w,wl_fixed_t x,wl_fixed_t y) { (void)d;(void)o;(void)s;(void)x;(void)y;pointer_focus=w==surface; }
static void ptr_leave(void *d,struct wl_pointer *o,uint32_t s,struct wl_surface *w) { (void)d;(void)o;(void)s;(void)w;pointer_focus=0; }
static void motion(void *d,struct wl_pointer *o,uint32_t t,wl_fixed_t x,wl_fixed_t y) { (void)d;(void)o;(void)x;(void)y;if(pointer_focus)note("motion",t); }
static void button(void *d,struct wl_pointer *o,uint32_t s,uint32_t t,uint32_t b,uint32_t state) { (void)d;(void)o;(void)s;(void)b;if(pointer_focus)note(state?"button_down":"button_up",t); }
static void axis(void *d,struct wl_pointer *o,uint32_t t,uint32_t a,wl_fixed_t v) { (void)d;(void)o;(void)t;(void)a;(void)v; }
static const struct wl_pointer_listener ptr_listener = {.enter=ptr_enter,.leave=ptr_leave,.motion=motion,.button=button,.axis=axis};
static void capabilities(void *d,struct wl_seat *o,uint32_t caps) {
    (void)d;
    if ((caps&WL_SEAT_CAPABILITY_KEYBOARD) && !keyboard) { keyboard=wl_seat_get_keyboard(o); wl_keyboard_add_listener(keyboard,&key_listener,NULL); }
    if ((caps&WL_SEAT_CAPABILITY_POINTER) && !pointer) { pointer=wl_seat_get_pointer(o); wl_pointer_add_listener(pointer,&ptr_listener,NULL); }
    if (!(caps&WL_SEAT_CAPABILITY_KEYBOARD)) key_focus=0;
    if (!(caps&WL_SEAT_CAPABILITY_POINTER)) pointer_focus=0;
}
static const struct wl_seat_listener seat_listener = {.capabilities=capabilities};
static void ping(void *d,struct wl_proxy *o,uint32_t serial) { (void)d;REQ(o,3,NULL,serial); }
static void configure(void *d,struct wl_proxy *o,uint32_t serial) { (void)d;REQ(o,4,NULL,serial);configured=1; }
static void top_configure(void *d,struct wl_proxy *o,int32_t w,int32_t h,struct wl_array *a) { (void)d;(void)o;(void)a;if((w&&w!=WIDTH)||(h&&h!=HEIGHT))failed=1; }
static void top_close(void *d,struct wl_proxy *o) { (void)d;(void)o;stopping=1; }
static void (*base_listener[])(void) = {(void(*)(void))ping};
static void (*xdg_listener[])(void) = {(void(*)(void))configure};
static void (*top_listener[])(void) = {(void(*)(void))top_configure,(void(*)(void))top_close};
static void global(void *d,struct wl_registry *r,uint32_t n,const char *name,uint32_t version) {
    (void)d;
    if (!strcmp(name,"wl_compositor") && !compositor && version>=3) compositor=wl_registry_bind(r,n,&wl_compositor_interface,3);
    else if (!strcmp(name,"wl_shm") && !shm) shm=wl_registry_bind(r,n,&wl_shm_interface,1);
    else if (!strcmp(name,"wl_seat") && !seat) { seat=wl_registry_bind(r,n,&wl_seat_interface,1);wl_seat_add_listener(seat,&seat_listener,NULL); }
    else if (!strcmp(name,"xdg_wm_base") && !base) { base=wl_registry_bind(r,n,&xdg_wm_base_interface,1);wl_proxy_add_listener(base,base_listener,NULL); }
}
static void removed(void *d,struct wl_registry *r,uint32_t n) { (void)d;(void)r;(void)n; }
static const struct wl_registry_listener registry_listener = {.global=global,.global_remove=removed};
static int create_window(void) {
    int fd=(int)syscall(__NR_memfd_create,"loopy-latency-public",MFD_CLOEXEC); size_t length=2*WIDTH*HEIGHT*4;
    if(fd<0 || ftruncate(fd,(off_t)length)) { if(fd>=0)close(fd);return 0; }
    pixels=mmap(NULL,length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(pixels==MAP_FAILED) { pixels=NULL;close(fd);return 0; }
    struct wl_shm_pool *pool=wl_shm_create_pool(shm,fd,(int32_t)length);close(fd);if(!pool)return 0;
    for(int i=0;i<2;i++) { buffers[i]=wl_shm_pool_create_buffer(pool,i*WIDTH*HEIGHT*4,WIDTH,HEIGHT,WIDTH*4,WL_SHM_FORMAT_XRGB8888);if(!buffers[i])return 0;wl_buffer_add_listener(buffers[i],&buffer_listener,(void*)(uintptr_t)i); }
    wl_shm_pool_destroy(pool);surface=wl_compositor_create_surface(compositor);if(!surface)return 0;
    xdg=REQ(base,2,&xdg_surface_interface,NULL,surface);if(!xdg)return 0;wl_proxy_add_listener(xdg,xdg_listener,NULL);
    top=REQ(xdg,1,&xdg_toplevel_interface,NULL);if(!top)return 0;wl_proxy_add_listener(top,top_listener,NULL);
    char label[80];snprintf(label,sizeof(label),"loopy-latency-%s",nonce);
    REQ(top,2,NULL,label);REQ(top,3,NULL,label);REQ(top,7,NULL,WIDTH,HEIGHT);REQ(top,8,NULL,WIDTH,HEIGHT);
    wl_surface_commit(surface);return 1;
}
int main(int argc,char **argv) {
    const char *path=NULL;uint64_t uid=UINT64_MAX,pid=0,stamp=0,seconds=30;unsigned seen=0;
    if(argc%2!=1)return 2;
    for(int i=1;i<argc;i+=2) {
        unsigned bit=0;uint64_t *number=NULL;
        if(!strcmp(argv[i],"--nonce")){bit=1;nonce=argv[i+1];}else if(!strcmp(argv[i],"--session")){bit=2;session=argv[i+1];}
        else if(!strcmp(argv[i],"--display")){bit=4;path=argv[i+1];}else if(!strcmp(argv[i],"--expect-uid")){bit=8;number=&uid;}
        else if(!strcmp(argv[i],"--server-pid")){bit=16;number=&pid;}else if(!strcmp(argv[i],"--server-birth")){bit=32;number=&stamp;}
        else if(!strcmp(argv[i],"--seconds")){bit=64;number=&seconds;}else return 2;
        if(seen&bit || (number&&!decimal(argv[i+1],number)))return 2;seen|=bit;
    }
    if((seen&63)!=63||!identifier(nonce,0)||!identifier(session,1)||!path||path[0]!='/'||strlen(path)>100||
       !strstr(path,"/com.termux/lr/wayland-")||uid!=getuid()||!pid||pid>INT32_MAX||!stamp||seconds<1||seconds>60)return 2;
    if(getsid(0)!=getpid()&&setsid()<0)return 2;own_birth=birth(getpid());if(!own_birth)return 3;
    signal(SIGTERM,stop_signal);signal(SIGINT,stop_signal);signal(SIGPIPE,SIG_IGN);setvbuf(stdout,NULL,_IOLBF,0);
    server_pid=(pid_t)pid;server_birth=stamp;struct stat before,after;
    if(lstat(path,&before)||!S_ISSOCK(before.st_mode)||before.st_uid!=getuid())return 3;
    display=wl_display_connect(path);if(!display)return 3;
    if(!peer()||lstat(path,&after)||before.st_dev!=after.st_dev||before.st_ino!=after.st_ino){wl_display_disconnect(display);return 3;}
    struct wl_registry *registry=wl_display_get_registry(display);if(!registry){wl_display_disconnect(display);return 3;}
    wl_registry_add_listener(registry,&registry_listener,NULL);uint64_t deadline=now_ns()+seconds*1000000000u;
    while(!stopping&&!failed&&sequence<LIMIT&&now_ns()<deadline) {
        if(wl_display_dispatch_pending(display)<0){failed=1;break;}
        if(!surface&&compositor&&shm&&seat&&base&&!create_window()){failed=1;break;}draw();if(failed)break;
        if(wl_display_prepare_read(display)){continue;}
        int flush=wl_display_flush(display);if(flush<0&&errno!=EAGAIN){wl_display_cancel_read(display);failed=1;break;}
        struct pollfd p={.fd=wl_display_get_fd(display),.events=POLLIN|(flush<0?POLLOUT:0)};
        int result=poll(&p,1,25);
        if(result<0&&errno==EINTR){wl_display_cancel_read(display);continue;}
        if(result<0||p.revents&(POLLERR|POLLHUP|POLLNVAL)){wl_display_cancel_read(display);failed=1;break;}
        if(p.revents&POLLIN){if(wl_display_read_events(display)<0){failed=1;break;}}else wl_display_cancel_read(display);
    }
    if(frame)wl_callback_destroy(frame);
    if(top)wl_proxy_marshal_flags(top,0,NULL,1,WL_MARSHAL_FLAG_DESTROY);
    if(xdg)wl_proxy_marshal_flags(xdg,0,NULL,1,WL_MARSHAL_FLAG_DESTROY);
    if(surface)wl_surface_destroy(surface);
    for(int i=0;i<2;i++)if(buffers[i])wl_buffer_destroy(buffers[i]);
    if(keyboard)wl_keyboard_destroy(keyboard);if(pointer)wl_pointer_destroy(pointer);if(seat)wl_seat_destroy(seat);
    if(base)wl_proxy_marshal_flags(base,0,NULL,1,WL_MARSHAL_FLAG_DESTROY);
    wl_registry_destroy(registry);wl_display_flush(display);wl_display_disconnect(display);
    if(pixels)munmap(pixels,2*WIDTH*HEIGHT*4);
    if(failed||!ready)return 3;
    printf("{\"type\":\"DONE\",\"reason\":\"%s\",\"window_destroyed\":true}\n",stopping?"own-close":sequence==LIMIT?"event-limit":"deadline");
    return ferror(stdout)?3:0;
}
