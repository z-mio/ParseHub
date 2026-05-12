import tempfile
import unittest
from pathlib import Path

from src.parsehub.cli_config import AutoCookieStore, ConfigStore, FileCookieStore, KeyringUnavailable


class UnavailableKeyringStore:
    def set(self, platform, cookie):
        raise KeyringUnavailable("unavailable")

    def get(self, platform):
        raise KeyringUnavailable("unavailable")

    def delete(self, platform):
        return False


class MemoryKeyringStore:
    def __init__(self):
        self.values = {}

    def set(self, platform, cookie):
        self.values[platform] = cookie

    def get(self, platform):
        return self.values.get(platform)

    def delete(self, platform):
        return self.values.pop(platform, None) is not None


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

    def test_auto_cookie_store_falls_back_to_private_file(self):
        path = self.base / "cookies.toml"
        store = AutoCookieStore(keyring_store=UnavailableKeyringStore(), file_store=FileCookieStore(path))

        storage = store.set("xhs", "a=b")

        self.assertEqual(storage, "file")
        self.assertEqual(store.get("xhs"), "a=b")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_auto_cookie_store_prefers_keyring_and_removes_file_fallback(self):
        path = self.base / "cookies.toml"
        file_store = FileCookieStore(path)
        file_store.set("xhs", "old=file")
        keyring_store = MemoryKeyringStore()
        store = AutoCookieStore(keyring_store=keyring_store, file_store=file_store)

        storage = store.set("xhs", "new=keyring")

        self.assertEqual(storage, "keyring")
        self.assertEqual(store.get("xhs"), "new=keyring")
        self.assertFalse(file_store.exists("xhs"))


if __name__ == "__main__":
    unittest.main()
