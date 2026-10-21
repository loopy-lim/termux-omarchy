import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


class CodeSizeTests(unittest.TestCase):
    def test_cpp_and_header_modules_cannot_bypass_the_source_limit(self):
        spec = importlib.util.spec_from_file_location('size_check',
            Path(__file__).resolve().parents[1] / 'tools/check_code_size.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as folder:
            checker.ROOT = Path(folder)
            for suffix in ('.cpp', '.hpp'):
                path = checker.ROOT / ('allocator' + suffix)
                path.write_text('// native module\n' * 501)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(checker.main(), 1)
            self.assertIn('allocator.cpp: 501', errors.getvalue())
            self.assertIn('allocator.hpp: 501', errors.getvalue())

    def test_packaged_nerd_font_is_a_binary_asset_while_guest_configuration_is_checked(self):
        spec = importlib.util.spec_from_file_location('size_check',
            Path(__file__).resolve().parents[1] / 'tools/check_code_size.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as folder:
            checker.ROOT = Path(folder)
            guest = checker.ROOT / 'guest/desktop/usr/share/fonts'
            guest.mkdir(parents=True)
            (guest / 'font.ttf').write_bytes(b'\x00\x01\x00\x00\xff')
            vendor = checker.ROOT / 'guest/desktop/usr/share/loopy/shell/powerlevel10k/internal'
            vendor.mkdir(parents=True)
            (vendor / 'p10k.zsh').write_text('# pinned upstream\n' * 1000)
            config = checker.ROOT / 'guest/desktop/.zshrc'
            config.write_text('# configuration\n' * 501)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(checker.main(), 1)
            self.assertIn('.zshrc: 501', errors.getvalue())
            self.assertNotIn('powerlevel10k', errors.getvalue())

    def test_collected_primary_evidence_is_excluded_but_product_code_is_checked(self):
        spec = importlib.util.spec_from_file_location('size_check',
            Path(__file__).resolve().parents[1] / 'tools/check_code_size.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as folder:
            checker.ROOT = Path(folder)
            evidence = checker.ROOT / 'docs/validation/run/primary/upstream.c'
            evidence.parent.mkdir(parents=True)
            evidence.write_text('/* upstream */\n' * 1000)
            implementation = checker.ROOT / 'native/product.c'
            implementation.parent.mkdir()
            implementation.write_text('/* local */\n' * 500)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(checker.main(), 0)
            implementation.write_text('/* local */\n' * 501)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(checker.main(), 1)
            self.assertIn('native/product.c: 501', errors.getvalue())
            self.assertNotIn('upstream.c', errors.getvalue())
