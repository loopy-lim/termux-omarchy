"""Exercise the standalone caller without opening a browser or touching profiles."""
import configparser
import shlex
from unittest import mock

import test_omarchy_webapp_launch as shared


class StandaloneWebappTests(shared.WebappAudioTests):
    def setUp(self):
        patcher = mock.patch.object(shared, 'SOURCE', shared.ROOT / 'termux/loopy-launch-webapp')
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_default_launch_reuses_profile_without_overrides(self):
        row = self.run_webapp(['https://www.notion.so/'])
        self.assertEqual(row['argv'], ['--no-sandbox', '--disable-dev-shm-usage',
                                      '--password-store=basic', '--app=https://www.notion.so/'])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ['.config'])

    def test_entries_use_fixed_official_urls_and_existing_icon(self):
        for name, url in (('Notion', 'https://www.notion.so/'),
                          ('Figma', 'https://www.figma.com/files')):
            with self.subTest(name=name):
                path = shared.ROOT / 'termux' / (name + '.desktop')
                parser = configparser.ConfigParser(interpolation=None)
                parser.optionxform = str
                parser.read_string(path.read_text())
                self.assertEqual(parser.sections(), ['Desktop Entry'])
                entry = parser['Desktop Entry']
                self.assertEqual(entry['Name'], name)
                self.assertEqual(entry['Type'], 'Application')
                self.assertEqual(entry['Terminal'], 'false')
                self.assertEqual(entry['Icon'], 'chromium')
                self.assertNotIn('StartupWMClass', entry)
                argv = shlex.split(entry['Exec'])
                self.assertEqual(argv, ['/usr/local/bin/loopy-launch-webapp', url])
                row = self.run_webapp(argv[1:])
                self.assertEqual(row['argv'][-1], '--app=' + url)


if __name__ == '__main__':
    shared.unittest.main()
