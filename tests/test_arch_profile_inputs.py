"""Production packaging must refuse a missing or corrupted prepared profile."""
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.arch_profile_inputs import checked_inputs
from tools import arch_profile_inputs

ROOT = Path(__file__).resolve().parents[1]


class ArchProfileInputsTests(unittest.TestCase):
    def test_compositor_update_can_reuse_cache_only_with_identical_other_inventory(self):
        before = {'files': {'usr/bin/zsh': {'sha256': 'compiler'},
            'usr/share/zsh/functions/Completion/_git': {'sha256': 'completion'},
            'usr/bin/Hyprland': {'sha256': 'old'}}}
        after = {'files': {**before['files'], 'usr/bin/Hyprland': {'sha256': 'new'}}}
        check = getattr(arch_profile_inputs, 'check_compositor_only_update', None)
        self.assertIsNotNone(check, 'image transition needs an actual cache compatibility check')
        check(before, after)
        for name in ('usr/bin/zsh', 'usr/share/zsh/functions/Completion/_git'):
            changed = {'files': {**after['files'], name: {'sha256': 'different'}}}
            with self.assertRaises(ValueError): check(before, changed)
        with self.assertRaises(ValueError): check(before, {'files': {**after['files'], 'usr/bin/extra': {}}})

    def test_existing_alpine_only_project_does_not_require_an_arch_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(checked_inputs(Path(directory)), [])

    def test_arch_catalog_cannot_be_packaged_without_its_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); assets = root / 'android/assets'; assets.mkdir(parents=True)
            (assets / 'omarchy-runtime.properties').write_text('public fixture catalog')
            with self.assertRaises(ValueError): checked_inputs(root)

    def test_modified_profile_bytes_are_rejected_before_native_provenance_or_source_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); assets = root / 'android/assets'; assets.mkdir(parents=True)
            original = ROOT / 'android/assets/arch-profile.tar.gz'
            if not original.is_file(): self.skipTest('prepared public profile required')
            shutil.copyfile(original.with_name('arch-profile.provenance.json'), assets / 'arch-profile.provenance.json')
            changed = bytearray(original.read_bytes()); changed[len(changed) // 2] ^= 1
            (assets / original.name).write_bytes(changed)
            with self.assertRaises(ValueError): checked_inputs(root)
