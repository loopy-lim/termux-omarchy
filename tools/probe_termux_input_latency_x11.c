/* Native Bionic/Xlib public fixture. XSync is server processing, not scan-out. */
#define _GNU_SOURCE
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define FUNCTIONS(F) \
 F(XOpenDisplay) F(XCloseDisplay) F(XDefaultScreen) F(XRootWindow) \
 F(XCreateSimpleWindow) F(XStoreName) F(XSetClassHint) F(XInternAtom) \
 F(XChangeProperty) F(XSetWMProtocols) F(XSelectInput) F(XMapRaised) \
 F(XSetInputFocus) F(XGetInputFocus) F(XCreateGC) F(XSetForeground) \
 F(XFillRectangle) F(XSync) F(XPending) F(XNextEvent) F(XConnectionNumber) \
 F(XDestroyWindow) F(XFreeGC) F(XSetErrorHandler) F(XSetIOErrorHandler) \
 F(XSetWMNormalHints)
#define DECLARE(name) static __typeof__(name) *a_##name;
FUNCTIONS(DECLARE)
static volatile sig_atomic_t stopping;
static int x_error;

static void stop_signal(int sig) { (void)sig; stopping = 1; }
static int error_handler(Display *d, XErrorEvent *e) { (void)d; (void)e; x_error = 1; return 0; }
static int io_error_handler(Display *d) { (void)d; _exit(3); }
static uint64_t now_ns(void) {
    struct timespec v;
    if (clock_gettime(CLOCK_MONOTONIC, &v)) _exit(3);
    return (uint64_t)v.tv_sec * 1000000000u + (uint64_t)v.tv_nsec;
}
static int decimal(const char *s, uint64_t *out) {
    if (!s || !*s) return 0;
    for (const char *p = s; *p; p++) if (*p < '0' || *p > '9') return 0;
    errno = 0; char *end; uint64_t n = strtoull(s, &end, 10);
    if (errno || *end) return 0;
    *out = n; return 1;
}
static int lower_hex(char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }
static int nonce_ok(const char *s) {
    if (strlen(s) != 32) return 0;
    for (int i = 0; i < 32; i++) if (!lower_hex(s[i])) return 0;
    return 1;
}
static int session_ok(const char *s) {
    if (strlen(s) != 36) return 0;
    for (int i = 0; i < 36; i++) {
        if (i == 8 || i == 13 || i == 18 || i == 23) { if (s[i] != '-') return 0; }
        else if (!lower_hex(s[i])) return 0;
    }
    return 1;
}
static uint64_t birth(pid_t pid) {
    char path[64], buf[4096]; snprintf(path, sizeof(path), "/proc/%d/stat", pid);
    FILE *f = fopen(path, "re"); if (!f) return 0;
    size_t n = fread(buf, 1, sizeof(buf) - 1, f); int extra = fgetc(f); fclose(f);
    if (!n || extra != EOF) return 0;
    buf[n] = 0; char *p = strrchr(buf, ')'); if (!p || p[1] != ' ') return 0;
    p += 2; char *save, *word = strtok_r(p, " ", &save);
    for (int i = 0; i < 19 && word; i++) word = strtok_r(NULL, " ", &save);
    uint64_t v = 0; if (!word || !decimal(word, &v)) return 0;
    return v;
}
static int library(void) {
    void *handle = dlopen("libX11.so", RTLD_NOW | RTLD_LOCAL); if (!handle) return 0;
#define LOAD(name) a_##name = (__typeof__(a_##name))dlsym(handle, #name); if (!a_##name) return 0;
    FUNCTIONS(LOAD)
    return 1;
}
static int peer(Display *display, pid_t pid, uint64_t stamp) {
    struct ucred value; socklen_t size = sizeof(value);
    if (getsockopt(a_XConnectionNumber(display), SOL_SOCKET, SO_PEERCRED, &value, &size)) return 0;
    return size == sizeof(value) && value.pid == pid && value.uid == getuid() && birth(pid) == stamp;
}
static int paint(Display *display, Window window, GC gc, unsigned seq) {
    a_XSetForeground(display, gc, seq & 1 ? 0x31554a : 0x24344d);
    a_XFillRectangle(display, window, gc, 0, 0, 640, 420);
    a_XSetForeground(display, gc, 0xe8edf2);
    a_XFillRectangle(display, window, gc, 240, 130, 160, 160);
    a_XSync(display, False);
    return !x_error;
}

int main(int argc, char **argv) {
    const char *nonce = NULL, *session = NULL, *display_name = NULL;
    uint64_t uid = UINT64_MAX, server_pid = 0, server_birth = 0, seconds = 30;
    if (argc % 2 != 1) return 2;
    unsigned seen = 0;
    for (int i = 1; i < argc; i += 2) {
        unsigned bit;
        if (!strcmp(argv[i], "--nonce")) { bit = 1; nonce = argv[i+1]; }
        else if (!strcmp(argv[i], "--session")) { bit = 2; session = argv[i+1]; }
        else if (!strcmp(argv[i], "--display")) { bit = 4; display_name = argv[i+1]; }
        else if (!strcmp(argv[i], "--expect-uid")) { bit = 8; if (!decimal(argv[i+1], &uid)) return 2; }
        else if (!strcmp(argv[i], "--server-pid")) { bit = 16; if (!decimal(argv[i+1], &server_pid)) return 2; }
        else if (!strcmp(argv[i], "--server-birth")) { bit = 32; if (!decimal(argv[i+1], &server_birth)) return 2; }
        else if (!strcmp(argv[i], "--seconds")) { bit = 64; if (!decimal(argv[i+1], &seconds)) return 2; }
        else return 2;
        if (seen & bit) return 2; seen |= bit;
    }
    uint64_t screen = 0;
    if ((seen & 63) != 63 || !nonce_ok(nonce) || !session_ok(session) || display_name[0] != ':' ||
        !decimal(display_name + 1, &screen) || screen < 20 || screen > 99 || getuid() != uid ||
        server_pid < 1 || server_pid > INT32_MAX || !server_birth || seconds < 1 || seconds > 60) return 2;
    if (getsid(0) != getpid() && setsid() < 0) return 2;
    uint64_t own_birth = birth(getpid()); if (!own_birth || !library()) return 3;
    signal(SIGTERM, stop_signal); signal(SIGINT, stop_signal); signal(SIGPIPE, SIG_IGN);
    a_XSetErrorHandler(error_handler); a_XSetIOErrorHandler(io_error_handler);
    Display *display = a_XOpenDisplay(display_name);
    if (!display || !peer(display, (pid_t)server_pid, server_birth)) return 3;
    Window window = a_XCreateSimpleWindow(display, a_XRootWindow(display, a_XDefaultScreen(display)),
                                         32, 32, 640, 420, 0, 0, 0x24344d);
    if (!window) return 3;
    char label[80]; snprintf(label, sizeof(label), "Loopy latency %s", nonce);
    a_XStoreName(display, window, label);
    XClassHint hint = {(char *)label, (char *)"LoopyLatencyNative"}; a_XSetClassHint(display, window, &hint);
    XSizeHints size = {.flags = PMinSize | PMaxSize, .min_width = 640, .max_width = 640,
                      .min_height = 420, .max_height = 420};
    a_XSetWMNormalHints(display, window, &size);
    unsigned long pid = (unsigned long)getpid();
    a_XChangeProperty(display, window, a_XInternAtom(display, "_NET_WM_PID", False), XA_CARDINAL,
                      32, PropModeReplace, (unsigned char *)&pid, 1);
    a_XChangeProperty(display, window, a_XInternAtom(display, "LOOPY_LATENCY_NONCE", False), XA_STRING,
                      8, PropModeReplace, (const unsigned char *)nonce, 32);
    Atom deletion = a_XInternAtom(display, "WM_DELETE_WINDOW", False);
    a_XSetWMProtocols(display, window, &deletion, 1);
    a_XSelectInput(display, window, ExposureMask | KeyPressMask | KeyReleaseMask | ButtonPressMask |
                    ButtonReleaseMask | PointerMotionMask | StructureNotifyMask);
    GC gc = a_XCreateGC(display, window, 0, NULL); if (!gc) return 3;
    a_XMapRaised(display, window);
    a_XSetInputFocus(display, window, RevertToParent, CurrentTime);
    if (!paint(display, window, gc, 0)) return 3;
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("{\"type\":\"READY\",\"schema\":1,\"nonce\":\"%s\",\"session\":\"%s\","
           "\"uid\":%u,\"pid\":%d,\"birth\":%" PRIu64 ",\"sid\":%d,\"backend\":\"x11-xsync\","
           "\"width\":640,\"height\":420,\"window\":%lu}\n", nonce, session, getuid(), getpid(), own_birth, getsid(0), window);
    unsigned seq = 0; int destroyed = 0, failed = 0;
    const char *reason = "deadline";
    uint64_t deadline = now_ns() + seconds * 1000000000u;
    while (!stopping && now_ns() < deadline && seq < 2048 && !x_error) {
        if (!a_XPending(display)) {
            struct pollfd fd = {.fd = a_XConnectionNumber(display), .events = POLLIN};
            int r = poll(&fd, 1, 25);
            if (r < 0 && errno == EINTR) continue;
            if (r < 0 || fd.revents & (POLLERR | POLLHUP | POLLNVAL)) { failed = 1; break; }
            continue;
        }
        XEvent event; a_XNextEvent(display, &event);
        uint64_t arrival = now_ns();
        if (event.xany.window != window) continue;
        if (event.type == DestroyNotify) { destroyed = 1; reason = "own-close"; break; }
        if (event.type == ClientMessage && (Atom)event.xclient.data.l[0] == deletion) { reason = "own-close"; break; }
        if (event.type == Expose) { if (!paint(display, window, gc, seq)) failed = 1; continue; }
        const char *kind = NULL; Time source = 0;
        if (event.type == KeyPress || event.type == KeyRelease) {
            kind = event.type == KeyPress ? "key_down" : "key_up"; source = event.xkey.time;
        } else if (event.type == ButtonPress || event.type == ButtonRelease) {
            kind = event.type == ButtonPress ? "button_down" : "button_up"; source = event.xbutton.time;
        } else if (event.type == MotionNotify) { kind = "motion"; source = event.xmotion.time; }
        if (!kind) continue;
        Window focus; int revert; a_XGetInputFocus(display, &focus, &revert);
        if (focus != window) continue;
        if (!peer(display, (pid_t)server_pid, server_birth) || birth(getpid()) != own_birth) { failed = 1; break; }
        seq++;
        printf("{\"type\":\"EVENT\",\"id\":%u,\"kind\":\"%s\",\"arrival_ns\":%" PRIu64 ",\"source_ms\":%u}\n",
               seq, kind, arrival, (uint32_t)source);
        if (!paint(display, window, gc, seq)) { failed = 1; break; }
        printf("{\"type\":\"PAINT\",\"ids\":[%u],\"complete_ns\":%" PRIu64 "}\n", seq, now_ns());
    }
    if (stopping) reason = "own-close";
    if (seq == 2048) reason = "event-limit";
    a_XFreeGC(display, gc);
    if (!destroyed) { a_XDestroyWindow(display, window); a_XSync(display, False); destroyed = !x_error; }
    a_XCloseDisplay(display);
    if (failed || x_error || !destroyed) return 3;
    printf("{\"type\":\"DONE\",\"reason\":\"%s\",\"window_destroyed\":true}\n", reason);
    return ferror(stdout) ? 3 : 0;
}
