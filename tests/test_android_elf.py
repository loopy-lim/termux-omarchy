"""Reject malformed or 4KiB-only native binaries before APK publication."""
import struct
import unittest
from tests.elf_fixture import arm64_elf
from tools.android_elf import verify_android_elf


class AndroidElfTests(unittest.TestCase):
    def test_pie_and_static_loader_accept_sixteen_kib_alignment(self):
        for elf_type in (2, 3):
            with self.subTest(elf_type=elf_type):
                result = verify_android_elf(arm64_elf(elf_type=elf_type))
                self.assertEqual(result["page_size"], 16384)
                self.assertEqual(result["relro_ends"], [32768])

    def test_four_kib_load_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "16KiB LOAD"):
            verify_android_elf(arm64_elf(alignment=4096))

    def test_aligned_load_with_bad_relro_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "GNU_RELRO"):
            verify_android_elf(arm64_elf(relro_end=28672))

    def test_mismatched_segment_offset_and_address_is_rejected(self):
        data = bytearray(arm64_elf())
        struct.pack_into("<Q", data, 80, 4096)
        with self.assertRaisesRegex(ValueError, "16KiB LOAD"):
            verify_android_elf(data)

    def test_bad_header_architecture_and_segment_bounds_are_rejected(self):
        values = [b"not-ELF", arm64_elf()[:100]]
        wrong_arch = bytearray(arm64_elf())
        struct.pack_into("<H", wrong_arch, 18, 62)
        outside_file = bytearray(arm64_elf())
        struct.pack_into("<Q", outside_file, 96, len(outside_file) + 1)
        values.extend([wrong_arch, outside_file])
        for data in values:
            with self.subTest(data=data[:20]):
                with self.assertRaises(ValueError):
                    verify_android_elf(data)
