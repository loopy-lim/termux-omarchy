import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.build_omarchy_graphics import extract_source
from tools.prepare_hyprtoolkit import prepare


class HyprtoolkitPreparationTests(unittest.TestCase):
    def test_pinned_original_archive_reproduces_every_candidate_file(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root / 'build/omarchy-sources/hyprtoolkit-shm/loopy-source-receipt.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'source'
            receipt = prepare(output)
            self.assertEqual(receipt['upstream']['commit'], 'f8cbaf42e1f7fdc9c7565d7be3e935f6d56c7a39')
            self.assertEqual(receipt['source_files'], expected['source_files'])
            self.assertEqual(len(receipt['source_files']), 234)
            for name, digest in receipt['source_files'].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest, name)

    def test_existing_work_and_symlink_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            existing = root / 'existing'; existing.mkdir()
            marker = existing / 'user-work'; marker.write_text('preserve')
            link = root / 'linked'; link.symlink_to(existing, target_is_directory=True)
            for target in [existing, link]:
                with self.assertRaisesRegex(ValueError, 'preserved'):
                    prepare(target)
            self.assertEqual(marker.read_text(), 'preserve')
            self.assertTrue(link.is_symlink())

    def test_toolkit_archive_cannot_escape_or_install_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, kind in [('hyprtoolkit-pin/../escape', tarfile.REGTYPE),
                               ('hyprtoolkit-pin/link', tarfile.SYMTYPE)]:
                archive = root / 'source.tar.gz'
                with tarfile.open(archive, 'w:gz') as writer:
                    member = tarfile.TarInfo(name); member.type = kind; member.size = 1
                    writer.addfile(member, io.BytesIO(b'x'))
                with self.assertRaises(ValueError):
                    extract_source(archive, root / 'candidate', 'pin', project='hyprtoolkit')
                self.assertFalse((root / 'candidate').exists())
                self.assertFalse((root / 'escape').exists())


if __name__ == '__main__':
    unittest.main()
