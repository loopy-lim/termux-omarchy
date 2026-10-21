"""Real Pacman metadata boundaries and complete transaction resolution."""
import io
import tarfile
import unittest

try:
    from tools import omarchy_packages as packages
except ImportError:
    packages = None


def database(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for name, fields in entries:
            data = fields if isinstance(fields, bytes) else ''.join(
                '%' + key + '%\n' + '\n'.join(values) + '\n\n'
                for key, values in fields.items()).encode()
            member = tarfile.TarInfo(name); member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def record(name, **extra):
    result = {'NAME': [name], 'VERSION': ['1.0-1'], 'ARCH': ['aarch64'],
              'FILENAME': [name + '-1.0-1-aarch64.pkg.tar.zst'],
              'SHA256SUM': ['a' * 64], 'CSIZE': ['100'], 'ISIZE': ['500']}
    result.update(extra)
    return result


class OmarchyPackageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(packages, 'Arch package preparation has not been implemented')

    def parse(self, entries, repository='core'):
        return packages.parse_database(database(entries), repository,
                                       'https://ca.us.mirror.archlinuxarm.org/aarch64/core')

    def test_alarm_split_depends_and_providers_are_not_lost(self):
        result = self.parse([('aqua-1.0-1/depends', {'DEPENDS': ['mesa', 'libfoo.so=14-64'],
                                                'PROVIDES': ['libaqua.so=1-64']}),
                             ('aqua-1.0-1/desc', record('aqua'))])
        self.assertEqual(result[0]['depends'], ['mesa', 'libfoo.so=14-64'])
        self.assertEqual(result[0]['provides'], ['libaqua.so=1-64'])
        self.assertTrue(result[0]['url'].endswith('/aqua-1.0-1-aarch64.pkg.tar.zst'))

    def test_alarm_empty_dependency_member_is_a_valid_leaf_package(self):
        result = self.parse([('leaf-1.0-1/desc', record('leaf')),
                             ('leaf-1.0-1/depends', {})])
        self.assertEqual(result[0]['depends'], [])

    def test_zero_payload_metapackage_is_retained_but_corrupt_metadata_is_rejected(self):
        result = self.parse([('base-1/desc', record('base', ISIZE=['0'], DEPENDS=['bash']))])
        self.assertEqual(result[0]['installed_bytes'], 0)
        self.assertEqual(result[0]['depends'], ['bash'])
        with self.assertRaises(ValueError):
            packages.parse_fields(b'\x00' * 512)

    def test_corrupt_unrequested_entry_is_explicitly_quarantined_and_cannot_resolve(self):
        data = database([('good-1/desc', record('good')),
                         ('bad-1/desc', b'\x00' * 512),
                         ('bad-1/depends', {'DEPENDS': ['good']})])
        rejected = []
        try:
            result = packages.parse_database(data, 'extra', 'https://example.org/extra', rejected=rejected)
        except TypeError:
            self.fail('Repository auditing must record corrupt entries without discarding requests')
        self.assertEqual([p['name'] for p in result], ['good'])
        self.assertEqual(rejected[0]['directory'], 'bad-1')
        self.assertIn('metadata', rejected[0]['reason'])
        with self.assertRaises(packages.ResolutionError) as error:
            packages.resolve(result, ['bad', 'good'], compare=lambda a, b: 0)
        self.assertEqual(error.exception.unresolved, ['bad'])
        with self.assertRaises(ValueError):
            packages.parse_database(data, 'extra', 'https://example.org/extra')

    def test_inline_metadata_is_supported_and_unsafe_archives_are_rejected(self):
        result = self.parse([('foo-1.0-1/desc', record('foo', DEPENDS=['bar']))])
        self.assertEqual(result[0]['depends'], ['bar'])
        for name in ('../foo/desc', '/foo/desc'):
            with self.assertRaises(ValueError): self.parse([(name, record('foo'))])
        for change in ({'ARCH': ['x86_64']}, {'FILENAME': ['../foo.pkg.tar.zst']},
                       {'SHA256SUM': ['missing']}, {'CSIZE': ['-1']}, {'NAME': ['foo', 'bar']}):
            with self.assertRaises(ValueError): self.parse([('foo-1/desc', record('foo', **change))])

    def test_duplicate_metadata_and_package_names_are_rejected(self):
        entries = [('foo-1/desc', record('foo')), ('foo-1/desc', record('foo'))]
        with self.assertRaises(ValueError): self.parse(entries)
        with self.assertRaises(ValueError):
            self.parse([('foo-1/desc', record('foo')), ('foo-2/desc', record('foo'))])

    def test_transaction_resolves_virtual_abi_and_retains_all_requested_roots(self):
        index = self.parse([('hypr-1/desc', record('hypr', DEPENDS=['libfoo.so=14-64', 'mesa'])),
                            ('foo-1/desc', record('foo', PROVIDES=['libfoo.so=14-64'])),
                            ('mesa-1/desc', record('mesa', PROVIDES=['opengl-driver'])),
                            ('shell-1/desc', record('shell', DEPENDS=['hypr', 'opengl-driver']))])
        transaction = packages.resolve(index, ['shell', 'hypr'], compare=lambda a, b: (a > b) - (a < b))
        self.assertEqual({p['name'] for p in transaction}, {'shell', 'hypr', 'foo', 'mesa'})

    def test_missing_requests_and_abi_conflicts_never_silently_disappear(self):
        index = self.parse([('hypr-1/desc', record('hypr', DEPENDS=['libfoo.so=14-64'])),
                            ('foo-1/desc', record('foo', PROVIDES=['libfoo.so=13-64']))])
        with self.assertRaises(packages.ResolutionError) as error:
            packages.resolve(index, ['missing-app', 'hypr'], compare=lambda a, b: (a > b) - (a < b))
        self.assertIn('missing-app', error.exception.unresolved)
        self.assertIn('libfoo.so=14-64', error.exception.unresolved)

    def test_multiple_provider_choice_requires_an_explicit_policy(self):
        index = self.parse([('consumer-1/desc', record('consumer', DEPENDS=['driver'])),
                            ('cpu-1/desc', record('cpu', PROVIDES=['driver'])),
                            ('gpu-1/desc', record('gpu', PROVIDES=['driver']))])
        with self.assertRaises(packages.ResolutionError):
            packages.resolve(index, ['consumer'], compare=lambda a, b: 0)
        result = packages.resolve(index, ['consumer'], preferences={'driver': 'gpu'}, compare=lambda a, b: 0)
        self.assertEqual({p['name'] for p in result}, {'consumer', 'gpu'})

    def test_two_already_requested_fonts_satisfy_a_virtual_font_dependency(self):
        index = self.parse([('app-1/desc', record('app', DEPENDS=['ttf-font'])),
                            ('mono-1/desc', record('mono', PROVIDES=['ttf-font'])),
                            ('sans-1/desc', record('sans', PROVIDES=['ttf-font']))])
        try:
            result = packages.resolve(index, ['app', 'mono', 'sans'], compare=lambda a, b: 0)
        except packages.ResolutionError as error:
            self.fail('Existing valid providers satisfy the dependency: ' + str(error))
        self.assertEqual({p['name'] for p in result}, {'app', 'mono', 'sans'})

    def test_actual_package_constraints_use_the_comparison_contract(self):
        index = self.parse([('consumer-1/desc', record('consumer', DEPENDS=['foo>=2.0'])),
                            ('foo-1/desc', record('foo', VERSION=['2.1-1']))])
        calls = []
        def compare(a, b): calls.append((a, b)); return 1
        self.assertEqual(len(packages.resolve(index, ['consumer'], compare=compare)), 2)
        self.assertIn(('2.1-1', '2.0'), calls)

    def additions(self, index, installed, requested, **kwargs):
        try:
            return packages.resolve(index, requested, installed=installed,
                                    compare=lambda a, b: (a > b) - (a < b), **kwargs)
        except TypeError as error:
            self.fail('Missing installed-package preservation boundary: ' + str(error))

    def test_installed_root_is_preserved_even_when_repository_has_newer_version(self):
        index = self.parse([('editor-2/desc', record('editor', VERSION=['2-1']))])
        installed = [{'name': 'editor', 'version': '1-1', 'provides': [], 'conflicts': []}]
        self.assertEqual(self.additions(index, installed, ['editor']), [])

    def test_installed_soname_satisfies_new_app_without_replacing_library(self):
        index = self.parse([('app-1/desc', record('app', DEPENDS=['libfoo.so=14-64'])),
                            ('foo-2/desc', record('foo', VERSION=['2-1'], PROVIDES=['libfoo.so=15-64']))])
        installed = [{'name': 'foo', 'version': '1-1', 'provides': ['libfoo.so=14-64'], 'conflicts': []}]
        self.assertEqual([p['name'] for p in self.additions(index, installed, ['app'])], ['app'])

    def test_required_library_upgrade_is_unresolved_and_never_added_to_transaction(self):
        index = self.parse([('app-1/desc', record('app', DEPENDS=['foo>=2'])),
                            ('foo-2/desc', record('foo', VERSION=['2-1']))])
        installed = [{'name': 'foo', 'version': '1-1', 'provides': [], 'conflicts': []}]
        with self.assertRaises(packages.ResolutionError) as error:
            self.additions(index, installed, ['app'])
        self.assertEqual(error.exception.unresolved, ['foo>=2'])
        self.assertEqual([p['name'] for p in error.exception.selected], ['app'])

    def test_existing_driver_provider_precedes_repository_provider_preference(self):
        index = self.parse([('app-1/desc', record('app', DEPENDS=['driver'])),
                            ('fallback-1/desc', record('fallback', PROVIDES=['driver']))])
        installed = [{'name': 'gpu', 'version': '1-1', 'provides': ['driver'], 'conflicts': []}]
        self.assertEqual([p['name'] for p in self.additions(
            index, installed, ['app'], preferences={'driver': 'fallback'})], ['app'])

    def test_multiple_existing_font_providers_need_no_new_choice_or_installation(self):
        index = self.parse([('app-1/desc', record('app', DEPENDS=['ttf-font']))])
        installed = [{'name': name, 'version': '1-1', 'provides': ['ttf-font'], 'conflicts': []}
                     for name in ('mono', 'sans')]
        self.assertEqual([p['name'] for p in self.additions(index, installed, ['app'])], ['app'])

    def test_new_app_conflict_with_existing_driver_cannot_be_ignored(self):
        index = self.parse([('app-1/desc', record('app', CONFLICTS=['driver']))])
        installed = [{'name': 'gpu', 'version': '1-1', 'provides': ['driver'], 'conflicts': []}]
        with self.assertRaises(packages.ResolutionError) as error:
            self.additions(index, installed, ['app'])
        self.assertEqual(error.exception.unresolved, ['app conflicts with driver'])

    def test_existing_package_conflict_with_new_app_is_checked_in_reverse(self):
        index = self.parse([('app-1/desc', record('app'))])
        installed = [{'name': 'gpu', 'version': '1-1', 'provides': [], 'conflicts': ['app']}]
        with self.assertRaises(packages.ResolutionError) as error:
            self.additions(index, installed, ['app'])
        self.assertEqual(error.exception.unresolved, ['gpu conflicts with app'])

    def test_missing_original_requests_remain_visible_with_installed_inventory(self):
        index = self.parse([('app-1/desc', record('app'))])
        installed = [{'name': 'editor', 'version': '1-1', 'provides': ['nvim'], 'conflicts': []}]
        with self.assertRaises(packages.ResolutionError) as error:
            self.additions(index, installed, ['nvim', 'app', 'missing'])
        self.assertEqual(error.exception.unresolved, ['missing'])
        self.assertEqual([p['name'] for p in error.exception.selected], ['app'])

    def test_duplicate_or_malformed_installed_inventory_is_refused(self):
        good = {'name': 'editor', 'version': '1-1', 'provides': [], 'conflicts': []}
        for installed in ([good, good], [dict(good, provides=['invalid >= 2'])],
                          [dict(good, conflicts=['../outside'])], [dict(good, version='')]):
            with self.assertRaises(ValueError): self.additions([], installed, ['editor'])


if __name__ == '__main__':
    unittest.main()
