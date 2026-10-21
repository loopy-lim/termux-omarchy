"""A detached refresh candidate must reject incomplete or mismatched delivery evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
IMAGE = '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86'
STOCK = {
    'Aquamarine': ('/usr/lib/libaquamarine.so.0.15.1', 'libaquamarine.so.0.15.1',
                  '4b662e8a42595592378e970a5bdae1156f93ab909449d01c566be2d2c5bb4461', 1736888,
                  'hyprwm/aquamarine', 'f31c47a1b9d300847d8fc3108ad959448103dfc1', 'graphics_patches'),
    'Hyprland': ('/usr/bin/Hyprland', 'Hyprland',
                 '4491b2dbc8c6e15596ec05c4fbcefbaa2d97814e616dc619dd24be8be9662b92', 17319768,
                 'hyprwm/Hyprland', 'efb50993780079460b0cbed1363e2166a2de1d9f', 'hyprland_patches'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def elf(*, soname=None, needed=(), machine=183, search_path=None, path_tag=29):
    """Hand-built ELF64 dynamic table exercises the validator without running a compiler."""
    strings = bytearray(b'\0'); tags = []
    for tag, name in [(14, soname)] if soname else []:
        tags.append((tag, len(strings))); strings.extend(name.encode() + b'\0')
    for name in needed:
        tags.append((1, len(strings))); strings.extend(name.encode() + b'\0')
    if search_path is not None:
        tags.append((path_tag, len(strings))); strings.extend(search_path.encode() + b'\0')
    tags += [(5, 0x400200), (10, len(strings)), (0, 0)]
    dynamic = b''.join(struct.pack('<QQ', *tag) for tag in tags)
    data = bytearray(0x200 + len(strings))
    ident = b'\x7fELF\x02\x01\x01' + b'\0' * 9
    data[:64] = struct.pack('<16sHHIQQQIHHHHHH', ident, 3, machine, 1, 0, 64, 0,
                            0, 64, 56, 2, 0, 0, 0)
    data[64:120] = struct.pack('<IIQQQQQQ', 1, 5, 0, 0x400000, 0, len(data), len(data), 0x1000)
    data[120:176] = struct.pack('<IIQQQQQQ', 2, 6, 0xc0, 0x4000c0, 0,
                              len(dynamic), len(dynamic), 8)
    data[0xc0:0xc0 + len(dynamic)] = dynamic
    data[0x200:] = strings
    return bytes(data)


class RefreshInputsTests(unittest.TestCase):
    def setUp(self):
        module = ROOT / 'tools/omarchy_refresh_inputs.py'
        self.assertTrue(module.is_file(), 'Detached refresh candidates have no provenance gate')
        spec = importlib.util.spec_from_file_location('refresh_inputs', module)
        self.checked = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.checked)
        self.temporary = tempfile.TemporaryDirectory(prefix='loopy-refresh-inputs-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.candidate = self.root / 'build/omarchy-refresh-test'
        self.inputs = {}
        self.write('tools/omarchy_refresh_inputs.py', module.read_bytes())
        self.write('tools/build_omarchy_refresh.py', b'candidate producer\n', pin=True)
        self.write('tools/build_omarchy_graphics.py', b'existing graphics producer\n', pin=True)
        self.write('tools/build_hyprland_rootless.py', b'existing compositor producer\n', pin=True)
        self.write('android/assets/omarchy-runtime.properties', ('archive_sha256=' + IMAGE + '\n').encode())
        lock = {'graphics_sources': [], 'graphics_patches': [], 'hyprland_patches': []}
        patches = {}
        for component, (_, _, _, _, repo, commit, key) in STOCK.items():
            lock['graphics_sources'].append({'repo': repo, 'commit': commit})
            prior = self.patch(component.lower() + '-baseline', commit)
            lock[key] = [prior]
            patches[component] = [prior, self.patch(component.lower() + '-refresh', commit)]
        self.write_json('third_party/omarchy.lock.json', lock, pin=True)
        lock_sha = self.inputs['third_party/omarchy.lock.json']
        self.record = {'schema': 1, 'status': 'compiled-in-reference-vm', 'architecture': 'aarch64',
                       'build_exit': 0, 'base_image_sha256': IMAGE, 'components': {}, 'inputs': self.inputs}
        for component, (guest, filename, base, base_size, repo, commit, _) in STOCK.items():
            prefix = 'build/omarchy-refresh-test/' + component.lower()
            source_dir = prefix + '-source'
            source_path = source_dir + '/loopy-source-receipt.json'
            code = b'complete candidate source\n'
            self.write(source_dir + '/src/output.cpp', code)
            source = {'status': 'source-prepared', 'architecture': 'aarch64', 'lock_sha256': lock_sha,
                      'upstream': {'repo': repo, 'commit': commit}, 'patches': patches[component],
                      'source_files': {'src/output.cpp': sha(code)}}
            self.write_json(source_path, source, pin=True)
            binary_path = 'build/omarchy-refresh-test/components/' + filename
            data = elf(soname='libaquamarine.so.14') if component == 'Aquamarine' else \
                elf(needed=('libaquamarine.so.14', 'libc.so.6'))
            self.write(binary_path, data)
            build_path = prefix + '-build-receipt.json'
            build = dict(source, status='compiled-in-reference-vm', build_exit=0, uid=501,
                         producer_sha256=self.inputs['tools/build_omarchy_refresh.py'],
                         binaries={filename: {'path': '/var/tmp/loopy-refresh/' + filename,
                                              'sha256': sha(data), 'bytes': len(data)}})
            self.write_json(build_path, build, pin=True)
            self.record['components'][component] = {
                'guest': guest, 'binary': binary_path, 'binary_sha256': sha(data), 'binary_bytes': len(data),
                'base_binary_sha256': base, 'base_binary_bytes': base_size, 'source_directory': source_dir,
                'source_receipt': source_path, 'source_receipt_sha256': self.inputs[source_path],
                'build_receipt': build_path, 'build_receipt_sha256': self.inputs[build_path],
                'producer': 'tools/build_omarchy_refresh.py',
                'producer_sha256': self.inputs['tools/build_omarchy_refresh.py']}
        self.save_record()

    def write(self, name, data, *, pin=False):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        if pin: self.inputs[name] = sha(data)
        return path

    def write_json(self, name, value, *, pin=False):
        return self.write(name, (json.dumps(value, indent=2) + '\n').encode(), pin=pin)

    def patch(self, name, commit):
        patch = 'native/omarchy/patches/' + name + '.patch'
        metadata = 'native/omarchy/patches/' + name + '.json'
        self.write(patch, b'guarded patch\n', pin=True)
        preimage = b'upstream source\n' if name.endswith('baseline') else b'baseline source\n'
        postimage = b'baseline source\n' if name.endswith('baseline') else b'complete candidate source\n'
        self.write_json(metadata, {'upstream_commit': commit, 'patch_sha256': self.inputs[patch],
                                  'files': {'src/output.cpp': {'preimage_sha256': sha(preimage),
                                                             'patched_sha256': sha(postimage)}}}, pin=True)
        return {'patch': patch, 'patch_sha256': self.inputs[patch], 'metadata_file': metadata,
                'metadata_sha256': self.inputs[metadata], 'upstream_commit': commit}

    def save_record(self):
        self.write_json('build/omarchy-refresh-test/component-receipt.json', self.record)

    def check(self):
        return self.checked.checked_inputs(self.root, self.candidate)

    def edit_receipt(self, component, key, change):
        item = self.record['components'][component]; path = item[key]
        record = json.loads((self.root / path).read_text()); change(record)
        self.write_json(path, record, pin=True); item[key + '_sha256'] = self.inputs[path]
        self.save_record()

    def test_valid_candidate_returns_all_verified_files_without_writing(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.check()
        self.assertIn(self.candidate / 'components/libaquamarine.so.0.15.1', result)
        self.assertIn(self.candidate / 'components/Hyprland', result)
        self.assertIn(self.candidate / 'aquamarine-source/src/output.cpp', result)
        self.assertIn(self.candidate / 'hyprland-source/src/output.cpp', result)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_rejects_any_binary_source_producer_or_receipt_drift(self):
        self.check()
        for name in ('components/Hyprland', 'components/libaquamarine.so.0.15.1',
                     'hyprland-source/src/output.cpp', 'aquamarine-source/src/output.cpp',
                     'aquamarine-build-receipt.json', 'hyprland-build-receipt.json'):
            path = self.candidate / name; old = path.read_bytes(); path.write_bytes(old + b'changed')
            with self.assertRaises(ValueError, msg=name): self.check()
            path.write_bytes(old)
        producer = self.root / 'tools/build_omarchy_refresh.py'; producer.write_bytes(b'different producer')
        with self.assertRaises(ValueError): self.check()

    def test_cannot_relabel_a_different_image_stock_binary_or_guest_path(self):
        for name in ('Aquamarine', 'Hyprland'):
            item = self.record['components'][name]
            for key, value in [('base_binary_sha256', '0' * 64), ('base_binary_bytes', 1),
                               ('guest', '/home/user/Hyprland')]:
                old = item[key]; item[key] = value; self.save_record()
                with self.assertRaises(ValueError, msg=key): self.check()
                item[key] = old
        self.record['base_image_sha256'] = '0' * 64; self.save_record()
        with self.assertRaises(ValueError): self.check()

    def test_rejects_failed_privileged_or_different_source_build_evidence(self):
        for field, value in [('build_exit', 1), ('status', 'source-prepared'), ('architecture', 'x86_64'),
                             ('uid', 0), ('source_files', {}), ('patches', []), ('producer_sha256', '0' * 64)]:
            path = self.candidate / 'aquamarine-build-receipt.json'; old = path.read_bytes()
            self.edit_receipt('Aquamarine', 'build_receipt', lambda r: r.update({field: value}))
            with self.assertRaises(ValueError, msg=field): self.check()
            self.write('build/omarchy-refresh-test/aquamarine-build-receipt.json', old, pin=True)
            self.record['components']['Aquamarine']['build_receipt_sha256'] = sha(old); self.save_record()

    def test_rejects_unlisted_source_and_source_symlinks(self):
        added = self.write('build/omarchy-refresh-test/aquamarine-source/CMakeLists.txt', b'injected build')
        with self.assertRaises(ValueError): self.check()
        added.unlink()
        code = self.candidate / 'aquamarine-source/src/output.cpp'; data = code.read_bytes(); code.unlink()
        external = self.write('different/source.cpp', data); code.symlink_to(external)
        with self.assertRaises(ValueError): self.check()

    def test_rejects_parent_escape_absolute_paths_and_candidate_symlinks(self):
        item = self.record['components']['Hyprland']; original = item['binary']
        for name in ('../outside', str(self.candidate / 'components/Hyprland')):
            item['binary'] = name; self.save_record()
            with self.assertRaises(ValueError): self.check()
        item['binary'] = original; self.save_record()
        link = self.root / 'build/linked-candidate'; link.symlink_to(self.candidate, target_is_directory=True)
        with self.assertRaises(ValueError): self.checked.checked_inputs(self.root, link)

    def test_rejects_missing_component_or_unpinned_patch_metadata(self):
        item = self.record['components'].pop('Aquamarine'); self.save_record()
        with self.assertRaises(ValueError): self.check()
        self.record['components']['Aquamarine'] = item
        key = 'native/omarchy/patches/aquamarine-refresh.json'; self.inputs.pop(key); self.save_record()
        with self.assertRaises(ValueError): self.check()

    def test_matching_receipts_cannot_hide_wrong_architecture_or_library_abi(self):
        for component, data in [('Aquamarine', elf(soname='libaquamarine.so.99')),
                                ('Aquamarine', elf(soname='libaquamarine.so.14', machine=62)),
                                ('Hyprland', elf(needed=('libaquamarine.so.99',))),
                                ('Aquamarine', elf(soname='libaquamarine.so.14', needed=('libX11.so.6',))),
                                ('Aquamarine', elf(soname='libaquamarine.so.14', needed=('libc.so.6', 'libc.so.6'))),
                                ('Aquamarine', elf(soname='libaquamarine.so.14', search_path='/var/tmp/other')),
                                ('Hyprland', elf(needed=('libaquamarine.so.14',), search_path='/usr/local/lib', path_tag=15))]:
            item = self.record['components'][component]; original = dict(item)
            old = (self.root / item['binary']).read_bytes()
            build_old = (self.root / item['build_receipt']).read_bytes()
            self.write(item['binary'], data); item['binary_sha256'] = sha(data); item['binary_bytes'] = len(data)
            filename = STOCK[component][1]
            self.edit_receipt(component, 'build_receipt', lambda r: r['binaries'][filename].update(
                sha256=sha(data), bytes=len(data)))
            with self.assertRaises(ValueError, msg=component): self.check()
            self.write(item['binary'], old); self.write(item['build_receipt'], build_old, pin=True)
            item.update(original); self.save_record()

    def test_matching_source_receipts_cannot_hide_a_dropped_guarded_patch(self):
        data = b'dropped refresh implementation\n'
        self.write('build/omarchy-refresh-test/aquamarine-source/src/output.cpp', data)
        for key in ('source_receipt', 'build_receipt'):
            self.edit_receipt('Aquamarine', key, lambda r: r['source_files'].update({'src/output.cpp': sha(data)}))
        with self.assertRaises(ValueError): self.check()

    def test_broken_patch_preimage_chain_is_rejected_even_with_matching_inputs(self):
        name = 'native/omarchy/patches/aquamarine-refresh.json'
        metadata = json.loads((self.root / name).read_text())
        metadata['files']['src/output.cpp']['preimage_sha256'] = '0' * 64
        self.write_json(name, metadata, pin=True)
        for key in ('source_receipt', 'build_receipt'):
            self.edit_receipt('Aquamarine', key, lambda r: r['patches'][-1].update(metadata_sha256=self.inputs[name]))
        with self.assertRaises(ValueError): self.check()

    def test_cli_reports_reviewable_bind_values_without_claiming_refresh_acceptance(self):
        result = subprocess.run([sys.executable, str(self.root / 'tools/omarchy_refresh_inputs.py'),
                                 '--root', str(self.root), '--candidate', str(self.candidate)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'candidate-inputs-verified')
        self.assertFalse(report['physical_device']); self.assertFalse(report['refresh_acceptance'])
        binds = {entry['component']: entry for entry in report['bindings']}
        self.assertEqual(binds['Aquamarine']['guest'], '/usr/lib/libaquamarine.so.0.15.1')
        self.assertEqual(binds['Hyprland']['guest'], '/usr/bin/Hyprland')
        self.assertEqual(binds['Aquamarine']['base_bytes'], 1736888)
        self.assertEqual(binds['Hyprland']['base_bytes'], 17319768)

    def test_malformed_nested_receipts_fail_closed_as_validation_errors(self):
        for field, value in [('binaries', []), ('upstream', []), ('source_files', []), ('patches', {})]:
            original = (self.candidate / 'aquamarine-build-receipt.json').read_bytes()
            self.edit_receipt('Aquamarine', 'build_receipt', lambda r: r.update({field: value}))
            with self.assertRaises(ValueError, msg=field): self.check()
            self.write('build/omarchy-refresh-test/aquamarine-build-receipt.json', original, pin=True)
            self.record['components']['Aquamarine']['build_receipt_sha256'] = sha(original); self.save_record()

    def audit_aquamarine_record(self):
        item = self.record['components']['Aquamarine']
        original = json.loads((self.root / item['build_receipt']).read_text())
        original['producer_sha256'] = '1' * 64
        name = 'build/omarchy-refresh-test/aquamarine-build-record-original.json'
        self.write_json(name, original, pin=True)
        audited = dict(original, producer_sha256=self.inputs['tools/build_omarchy_refresh.py'],
                       provenance_role='audited-re-record', original_build_receipt=name,
                       original_build_receipt_sha256=self.inputs[name], historical_producer_sha256='1' * 64,
                       audit_tool='tools/omarchy_refresh_inputs.py',
                       audit_tool_sha256=sha((self.root / 'tools/omarchy_refresh_inputs.py').read_bytes()),
                       audit_method='host-source-binary-and-record-equality; no rebuild',
                       audited_at='2026-10-08T00:00:00Z')
        self.inputs['tools/omarchy_refresh_inputs.py'] = audited['audit_tool_sha256']
        self.write_json(item['build_receipt'], audited, pin=True)
        item['build_receipt_sha256'] = self.inputs[item['build_receipt']]; self.save_record()
        return name

    def test_audited_re_record_keeps_and_pins_exact_original_build_evidence(self):
        original = self.audit_aquamarine_record()
        result = self.check(); self.assertIn(self.root / original, result)
        path = self.root / original; path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaises(ValueError): self.check()

    def test_audit_cannot_change_original_commands_or_hide_historical_producer(self):
        self.audit_aquamarine_record()
        self.edit_receipt('Aquamarine', 'build_receipt', lambda r: r.update(build_commands=[['invented', 'build']]))
        with self.assertRaises(ValueError): self.check()

    def test_audit_requires_known_recorder_and_explicit_no_rebuild_role(self):
        self.audit_aquamarine_record()
        self.edit_receipt('Aquamarine', 'build_receipt', lambda r: r.update(audit_tool='tools/other.py'))
        with self.assertRaises(ValueError): self.check()


if __name__ == '__main__': unittest.main()
