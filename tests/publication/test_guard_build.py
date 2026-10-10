"""Release preparation must reject untrusted inputs before producing files."""
import hashlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def archive(rows):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as output:
        for name, content, kind in rows:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(content)
                output.addfile(member, io.BytesIO(content))
            else:
                member.linkname = content.decode()
                output.addfile(member)
    return data.getvalue()


class GuardBuildTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'native/guard/build.py'
        self.assertTrue(path.is_file(), 'public guard preparation is missing')
        spec = importlib.util.spec_from_file_location('guard_build', path)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def test_changed_source_archive_is_rejected_without_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'source'
            data = archive([('upstream/file.c', b'changed', tarfile.REGTYPE)])
            with self.assertRaisesRegex(ValueError, 'source-checksum'):
                self.builder.extract_source(data, output, '0' * 64)
            self.assertFalse(output.exists())

    def test_archive_escape_is_rejected_before_any_source_is_written(self):
        rows = [('upstream/good.c', b'good', tarfile.REGTYPE),
                ('upstream/../../escaped.c', b'bad', tarfile.REGTYPE)]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'source'
            data = archive(rows)
            with self.assertRaisesRegex(ValueError, 'source-member'):
                self.builder.extract_source(data, output, hashlib.sha256(data).hexdigest())
            self.assertFalse(output.exists())
            self.assertFalse((Path(temporary) / 'escaped.c').exists())

    def test_source_symlink_cannot_redirect_later_archive_writes(self):
        rows = [('upstream/link', b'../outside', tarfile.SYMTYPE)]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'source'
            data = archive(rows)
            with self.assertRaisesRegex(ValueError, 'source-member'):
                self.builder.extract_source(data, output, hashlib.sha256(data).hexdigest())
            self.assertFalse(output.exists())

    def test_verified_source_has_one_stripped_top_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'source'
            data = archive([('upstream/src/file.c', b'owned source', tarfile.REGTYPE)])
            self.builder.extract_source(data, output, hashlib.sha256(data).hexdigest())
            self.assertEqual((output / 'src/file.c').read_bytes(), b'owned source')
            self.assertFalse((output / 'upstream').exists())

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / 'keep'
            marker.write_text('user content')
            with self.assertRaisesRegex(ValueError, 'output-exists'):
                self.builder.new_output(output)
            self.assertEqual(marker.read_text(), 'user content')

    def test_source_bundle_contains_rebuild_inputs_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / 'inputs'
            inputs.mkdir()
            (inputs / 'source.c').write_text('source')
            (inputs / 'COPYING').write_text('license')
            first, second = root / 'first.tar.gz', root / 'second.tar.gz'
            self.builder.source_archive(inputs, first)
            (inputs / 'source.c').touch()
            self.builder.source_archive(inputs, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as source:
                self.assertEqual(source.extractfile('guard-source/source.c').read(), b'source')
                self.assertEqual(source.extractfile('guard-source/COPYING').read(), b'license')

    def test_wrong_ndk_is_rejected_before_compilation(self):
        with tempfile.TemporaryDirectory() as temporary:
            ndk = Path(temporary)
            (ndk / 'source.properties').write_text('Pkg.Revision = 1.0.0\n')
            with self.assertRaisesRegex(ValueError, 'ndk-version'):
                self.builder.ndk_tools(ndk)

    def test_changed_build_feature_preset_fails_offline_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            builder = Path(temporary) / 'builder'
            shutil.copytree(ROOT / 'native/guard', builder)
            (builder / 'talloc-android-api28.h').write_text('#define WRONG_TARGET 1\n')
            result = subprocess.run([sys.executable, '-B', str(builder / 'build.py'), '--check'],
                                    text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('build-input-checksum', result.stderr)

    def test_relink_source_cannot_contain_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            for name in ('proot', 'talloc', 'android-shmem'):
                (source / name).mkdir()
            (source / 'talloc/outside').symlink_to(root / 'outside')
            with self.assertRaisesRegex(ValueError, 'relink-source-symlink'):
                self.builder.copy_relink_source(source, root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_relink_source_preserves_modified_library_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            for name in ('proot', 'talloc', 'android-shmem'):
                (source / name).mkdir()
            (source / 'talloc/talloc.c').write_text('modified library source')
            self.builder.copy_relink_source(source, root / 'output')
            self.assertEqual((root / 'output/talloc/talloc.c').read_text(),
                             'modified library source')

    def test_relink_source_cannot_reuse_supplied_object_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            for name in ('proot', 'talloc', 'android-shmem'):
                (source / name).mkdir()
            (source / 'talloc/talloc.o').write_bytes(b'old compiled object')
            with self.assertRaisesRegex(ValueError, 'relink-source-generated-file'):
                self.builder.copy_relink_source(source, root / 'output')
            self.assertFalse((root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
