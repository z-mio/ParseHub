import tempfile
import unittest
from pathlib import Path

from src.parsehub.cli_config import AutoCookieStore, ConfigStore, FileCookieStore


class TestCliConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_config_store_sets_and_clears_targeted_proxy(self):
        store = ConfigStore(self.base / "config.toml")

        store.set_proxy("xhs", "http://parse", "parse")
        store.set_proxy("xhs", "http://download", "download")

        config = store.get_platform("xhs")
        self.assertEqual(config.parse_proxy, "http://parse")
        self.assertEqual(config.download_proxy, "http://download")

        self.assertTrue(store.clear_proxy("xhs", "parse"))
        config = store.get_platform("xhs")
        self.assertIsNone(config.parse_proxy)
        self.assertEqual(config.download_proxy, "http://download")

    def test_auto_cookie_store_uses_private_file(self):
        path = self.base / "cookies.toml"
        store = AutoCookieStore(file_store=FileCookieStore(path))

        store.set("xhs", "a=b")

        self.assertEqual(store.get("xhs"), "a=b")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_auto_cookie_store_deletes_private_file_cookie(self):
        path = self.base / "cookies.toml"
        store = AutoCookieStore(file_store=FileCookieStore(path))
        store.set("xhs", "a=b")

        self.assertTrue(store.delete("xhs"))

        self.assertFalse(store.exists("xhs"))


if __name__ == "__main__":
    unittest.main()
