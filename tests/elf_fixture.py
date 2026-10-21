"""Small structurally valid ARM64 ELF for package validation tests."""
import struct


def arm64_elf(payload=b"fixture", alignment=16384, elf_type=3, relro_end=32768):
    data = bytearray(256 + len(payload))
    data[:16] = b"\x7fELF\x02\x01\x01" + bytes(9)
    struct.pack_into("<HHIQQQIHHHHHH", data, 16, elf_type, 183, 1,
                     0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0,
                     len(data), 32768, alignment)
    struct.pack_into("<IIQQQQQQ", data, 120, 0x6474e552, 4,
                     176, 176, 176, 16, relro_end - 176, 1)
    data[256:] = payload
    return bytes(data)
