/* Build twice (bionic and glibc); the two processes share exactly one fence word.
 * No device changes, privilege changes, or implicit cleanup of existing files. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <signal.h>

struct xshmfence;
static int (*f_alloc)(void);
static struct xshmfence *(*f_map)(int);
static void (*f_unmap)(struct xshmfence *);
static int (*f_await)(struct xshmfence *);
static int (*f_trigger)(struct xshmfence *);
static int (*f_query)(struct xshmfence *);
static void (*f_reset)(struct xshmfence *);

static void fail(const char *what) {
    fprintf(stderr, "FAIL %s errno=%d\n", what, errno);
    exit(1);
}
static void timeout_handler(int unused) {
    (void)unused;
    static const char message[] = "FAIL deadline\n";
    write(STDERR_FILENO, message, sizeof(message) - 1);
    _exit(124);
}
static void load_library(const char *path) {
    void *lib = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!lib) fail("dlopen");
#define LOAD(name, symbol) do { *(void **)(&name) = dlsym(lib, symbol); if (!name) fail(symbol); } while (0)
    LOAD(f_alloc, "xshmfence_alloc_shm"); LOAD(f_map, "xshmfence_map_shm");
    LOAD(f_unmap, "xshmfence_unmap_shm"); LOAD(f_await, "xshmfence_await");
    LOAD(f_trigger, "xshmfence_trigger"); LOAD(f_query, "xshmfence_query");
    LOAD(f_reset, "xshmfence_reset");
    int fd = f_alloc();
    struct stat st;
    if (fd < 0 || fstat(fd, &st)) fail("allocation");
    if (st.st_size != 4) {
        fprintf(stderr, "FAIL incompatible allocated fence size=%lld expected=4\n", (long long)st.st_size);
        exit(2);
    }
    close(fd);
}
static void command(unsigned cycle) {
    char line[64], expected[64];
    snprintf(expected, sizeof(expected), "GO %u\n", cycle);
    if (!fgets(line, sizeof(line), stdin) || strcmp(line, expected)) fail("handshake");
}

int main(int argc, char **argv) {
    if (argc < 4 || argc > 5) {
        fprintf(stderr, "usage: probe LIBRARY init FILE | probe LIBRARY wait|signal FILE before|after\n");
        return 2;
    }
    signal(SIGALRM, timeout_handler); alarm(60);
    setvbuf(stdout, NULL, _IOLBF, 0);
    load_library(argv[1]);
    int init = !strcmp(argv[2], "init");
    int waiter = !strcmp(argv[2], "wait");
    int sender = !strcmp(argv[2], "signal");
    int after = argc == 5 && !strcmp(argv[4], "after");
    if ((!init && !waiter && !sender) || (init && argc != 4) ||
        (!init && (argc != 5 || (!after && strcmp(argv[4], "before"))))) fail("arguments");
    int fd = open(argv[3], O_RDWR | O_CLOEXEC | O_NOFOLLOW |
                  (init ? O_CREAT | O_EXCL : 0), 0600);
    if (fd < 0) fail("open-owned-file");
    if (init && ftruncate(fd, 4)) fail("size");
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size != 4 ||
        st.st_nlink != 1 || st.st_uid != getuid() || (st.st_mode & 077)) fail("file-identity");
    struct xshmfence *fence = f_map(fd);
    if (!fence) fail("map");
    int32_t *word = mmap(NULL, 4, PROT_READ, MAP_SHARED, fd, 0);
    if (word == MAP_FAILED) fail("observe-map");
    close(fd);
    if (init) {
        if (f_query(fence)) fail("initially-triggered");
        puts("INIT 4");
    } else {
        for (unsigned cycle = 0; cycle < 20; ++cycle) {
            if (waiter) {
                if (f_query(fence)) fail("reset-not-observed");
                printf("READY %u\n", cycle);
                /* before: host lets the sender finish first; after: enter wait now. */
                if (!after) command(cycle);
                if (f_await(fence) || !f_query(fence)) fail("await-query");
                f_reset(fence);
                if (f_query(fence)) fail("reset");
                printf("DONE %u\n", cycle);
            } else {
                command(cycle);
                if (after) {
                    /* -1 is the upstream futex waiter's published waiting state. */
                    while (__atomic_load_n(word, __ATOMIC_ACQUIRE) != -1) usleep(1000);
                } else if (f_query(fence)) fail("unexpected-trigger");
                if (f_trigger(fence)) fail("trigger");
                printf("SENT %u\n", cycle);
            }
        }
        puts("PASS 20");
    }
    munmap(word, 4); f_unmap(fence); alarm(0);
    return 0;
}
