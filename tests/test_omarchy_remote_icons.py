"""Trusted raw icon caches retain GTK palette handling and source identities."""
import importlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OmarchyRemoteIconTests(unittest.TestCase):
    def module(self):
        self.assertTrue((ROOT / 'tools/omarchy_remote_icons.py').is_file(),
                        'trusted raw icon cache producer is missing')
        return importlib.import_module('tools.omarchy_remote_icons')

    def test_symbolic_lookup_and_mask_aliases_share_exact_raw_pixels(self):
        tool = self.module()
        pixels = bytes((12, 23, 34, 255)) * (32 * 32)
        data = tool.cache_bytes({'dialog-warning-symbolic': (pixels, True),
                                 'image-missing': (pixels, False)})
        entries = tool.cache_pixels(data)
        self.assertEqual(set(entries), {'dialog-warning-symbolic',
                                       'dialog-warning-symbolic.symbolic', 'image-missing'})
        self.assertEqual(entries['dialog-warning-symbolic'], pixels)
        self.assertEqual(entries['dialog-warning-symbolic.symbolic'], pixels)
        # Cache dimensions and pixel encoding are fixed, bounded raw RGBA.
        self.assertIn(struct.pack('>IIIIII', 0x47646B50, 4120, 0x01010002, 128, 32, 32), data)

    def test_injected_names_or_wrong_pixel_sizes_are_rejected(self):
        tool = self.module()
        for images in ({'../escape': (bytes(4096), False)},
                       {'bad\nname': (bytes(4096), False)},
                       {'image-missing': (bytes(8), False)}, {}):
            with self.subTest(images=list(images)), self.assertRaises(ValueError):
                tool.cache_bytes(images)

    def test_untrusted_or_corrupt_cache_is_rejected_without_decoding(self):
        tool = self.module()
        data = tool.cache_bytes({'image-missing': (bytes(4096), False)})
        for changed in (data[:-1], b'UNTRUSTED', data[:24] + bytes(4) + data[28:]):
            with self.subTest(size=len(changed)), self.assertRaises(ValueError):
                tool.cache_pixels(changed)

    def test_source_hash_and_generated_membership_are_bound_to_signed_manifests(self):
        tool = self.module()
        self.assertTrue(callable(getattr(tool, 'checked_icons', None)),
                        'signed source and generated cache binding is missing')
        original = {'usr/share/icons/Adwaita/scalable/status/image-missing.svg':
                    {'kind': 'file', 'sha256': 'a' * 64, 'owners': ['adwaita-icon-theme']}}
        generated = {'usr/share/icons/Adwaita/icon-theme.cache':
                     {'kind': 'file', 'sha256': 'b' * 64},
                     'usr/share/icons/Adwaita/index.theme': {'kind': 'file', 'sha256': 'c' * 64}}
        receipt = {'schema': 1, 'format': tool.FORMAT, 'decoder_policy_changed': False,
                   'external_images_accepted': False, 'themes': {'Adwaita':
                   {'cache_sha256': 'b' * 64, 'index_sha256': 'c' * 64}}, 'sources':
                   [{'theme': 'Adwaita', 'source': next(iter(original)), 'source_sha256': 'a' * 64}]}
        tool.checked_icons(receipt, generated, original)
        receipt['sources'][0]['source_sha256'] = 'd' * 64
        with self.assertRaises(ValueError): tool.checked_icons(receipt, generated, original)
        receipt['sources'][0]['source_sha256'] = 'a' * 64
        generated['usr/share/icons/Adwaita/icon-theme.cache']['sha256'] = 'e' * 64
        with self.assertRaises(ValueError): tool.checked_icons(receipt, generated, original)

    def test_remmina_sources_exclude_previously_generated_rasters(self):
        tool = self.module()
        files = {'usr/share/icons/hicolor/apps/original.svg': {'kind': 'file', 'owners': ['remmina']},
                 'usr/share/icons/hicolor/32x32/icons/original.png':
                 {'kind': 'file', 'owners': ['reference-public-setup']}}
        self.assertTrue(callable(getattr(tool, 'remote_icon_files', None)),
                        'rebuilding must select original signed Remmina members')
        self.assertEqual(set(tool.remote_icon_files(files)), {'usr/share/icons/hicolor/apps/original.svg'})


if __name__ == '__main__':
    unittest.main()
