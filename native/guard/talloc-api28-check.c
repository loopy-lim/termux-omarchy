/* Target checks for the reviewed talloc feature preset. 2026-10-10. */
#include "config.h"
#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>

#if !defined(__ANDROID__) || __ANDROID_API__ != 28 || !defined(__aarch64__)
#error This preset requires the Android ARM64 API 28 compiler.
#endif
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error This preset requires little-endian ARM64.
#endif
_Static_assert(sizeof(void *) == 8, "pointer ABI");
_Static_assert(sizeof(long) == 8, "long ABI");
_Static_assert(sizeof(off_t) == 8, "file offset ABI");
_Static_assert(sizeof(size_t) == 8, "size ABI");
_Static_assert(sizeof(uintptr_t) == 8, "uintptr ABI");
