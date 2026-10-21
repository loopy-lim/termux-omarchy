/* Public-fixture identity only: no command lines or keyboard content. */
#ifndef LOOPY_LATENCY_IDENTITY_H
#define LOOPY_LATENCY_IDENTITY_H
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
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
static int identifier(const char *s, int uuid) {
    size_t length = uuid ? 36 : 32;
    if (!s || strlen(s) != length) return 0;
    for (size_t i = 0; i < length; i++) {
        if (uuid && (i == 8 || i == 13 || i == 18 || i == 23)) { if (s[i] != '-') return 0; }
        else if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f'))) return 0;
    }
    return 1;
}
static uint64_t birth(pid_t pid) {
    char path[64], buf[4096]; snprintf(path, sizeof(path), "/proc/%d/stat", pid);
    FILE *f = fopen(path, "re"); if (!f) return 0;
    size_t n = fread(buf, 1, sizeof(buf)-1, f); int extra = fgetc(f); fclose(f);
    if (!n || extra != EOF) return 0;
    buf[n] = 0; char *p = strrchr(buf, ')'); if (!p || p[1] != ' ') return 0;
    p += 2; char *save, *word = strtok_r(p, " ", &save);
    for (int i = 0; i < 19 && word; i++) word = strtok_r(NULL, " ", &save);
    uint64_t value = 0; return word && decimal(word, &value) ? value : 0;
}
static int owned_peer(int fd, pid_t pid, uint64_t stamp) {
    struct ucred value; socklen_t size = sizeof(value);
    return !getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &value, &size) && size == sizeof(value)
        && value.pid == pid && value.uid == getuid() && birth(pid) == stamp;
}
#endif
