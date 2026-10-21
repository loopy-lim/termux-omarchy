"""Check extracted Android ARM64 binaries for 16KiB loader alignment."""
import struct

PAGE_SIZE = 16384


def verify_android_elf(data):
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Android native input must be an ELF64 little-endian binary")
    elf_type, machine = struct.unpack_from("<HH", data, 16)
    if elf_type not in (2, 3) or machine != 183:
        raise ValueError("Android native input must be an ARM64 executable or shared library")
    offset = struct.unpack_from("<Q", data, 32)[0]
    header_size, size, count = struct.unpack_from("<HHH", data, 52)
    if header_size != 64 or size != 56 or not 0 < count <= 128 \
            or offset < 64 or offset + size * count > len(data):
        raise ValueError("Android ELF program headers invalid")
    loads, relro = [], []
    for index in range(count):
        kind, flags, start, address, _, filesz, memsz, align = struct.unpack_from(
            "<IIQQQQQQ", data, offset + size * index)
        if start + filesz > len(data):
            raise ValueError("Android ELF segment outside file")
        if kind == 1:
            if filesz > memsz or align < PAGE_SIZE or align & (align - 1) \
                    or start % align != address % align:
                raise ValueError("Android ELF requires valid 16KiB LOAD alignment")
            loads.append({"offset": start, "address": address, "alignment": align})
        elif kind == 0x6474e552:
            end = address + memsz
            if end % PAGE_SIZE:
                raise ValueError("Android ELF requires a 16KiB aligned GNU_RELRO end")
            relro.append(end)
    if not loads:
        raise ValueError("Android ELF LOAD segment missing")
    return {"machine": "aarch64", "elf_type": elf_type, "page_size": PAGE_SIZE,
            "load_segments": loads, "relro_ends": relro}
