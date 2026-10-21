"""Address input and durable storage boundaries for the native Linux browser."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "guest/desktop/usr/local/lib/loopy/browser_policy.py"
spec = importlib.util.spec_from_file_location("browser_policy", PATH)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class BrowserPolicyTests(unittest.TestCase):
    def test_http_and_https_keep_path_query_and_fragment(self):
        for url in ("http://127.0.0.1:45379/a?x=1#form", "https://example.com/a?q=a%20b#part"):
            self.assertEqual(policy.address("  " + url + "  "), url)

    def test_loopback_defaults_http_and_public_host_defaults_https(self):
        for typed, expected in (("localhost:8080", "http://localhost:8080"),
                                ("127.0.0.1:8080/a", "http://127.0.0.1:8080/a"),
                                ("[::1]:8080", "http://[::1]:8080"),
                                ("example.com/a", "https://example.com/a")):
            self.assertEqual(policy.address(typed), expected)

    def test_search_quotes_words_in_one_query(self):
        self.assertEqual(policy.address("한글 browser & keyboard"),
                         "https://duckduckgo.com/?q=%ED%95%9C%EA%B8%80+browser+%26+keyboard")

    def test_invalid_schemes_controls_and_ports_fail_closed(self):
        for value in ("javascript:alert(1)", "data:text/html,test", "file:///root/secret",
                      "https://", "https://example.com:0", "https://example.com:99999",
                      "https://example.com/a\x00b", "https://example.com/a\nb"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.address(value)

    def test_blank_is_a_local_page(self):
        self.assertEqual(policy.address(""), "about:blank")
        self.assertEqual(policy.address("about:blank"), "about:blank")

    def test_xdg_paths_are_durable_and_existing_browser_data_is_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            existing = home / "firefox-profile"
            existing.write_text("keep", encoding="utf-8")
            env = {"HOME": folder, "XDG_DATA_HOME": str(home / "data"), "XDG_CACHE_HOME": str(home / "cache")}
            self.assertEqual(policy.profile_paths(env), (home / "data/loopy-browser", home / "cache/loopy-browser"))
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_relative_xdg_value_does_not_move_storage_with_working_directory(self):
        self.assertEqual(policy.profile_paths({"HOME": "/root", "XDG_DATA_HOME": "relative"}),
                         (Path("/root/.local/share/loopy-browser"), Path("/root/.cache/loopy-browser")))


if __name__ == "__main__":
    unittest.main()
