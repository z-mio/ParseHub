from __future__ import annotations

import getpass
import json
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ProxyTarget = Literal["parse", "download", "all"]


@dataclass(frozen=True)
class PlatformConfig:
    parse_proxy: str | None = None
    download_proxy: str | None = None


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = default_config_path() if path is None else Path(path)

    def get_platform(self, platform: str) -> PlatformConfig:
        data = _read_toml(self.path)
        item = data.get("platform", {}).get(platform, {})
        if not isinstance(item, dict):
            item = {}
        return PlatformConfig(
            parse_proxy=_optional_str(item.get("parse_proxy")),
            download_proxy=_optional_str(item.get("download_proxy")),
        )

    def list_platforms(self) -> dict[str, PlatformConfig]:
        data = _read_toml(self.path)
        platforms = data.get("platform", {})
        if not isinstance(platforms, dict):
            return {}
        return {platform: self.get_platform(platform) for platform in sorted(platforms)}

    def set_proxy(self, platform: str, proxy: str, target: ProxyTarget = "all") -> None:
        data = _read_toml(self.path)
        platform_data = data.setdefault("platform", {})
        if not isinstance(platform_data, dict):
            platform_data = {}
            data["platform"] = platform_data
        item = platform_data.setdefault(platform, {})
        if not isinstance(item, dict):
            item = {}
            platform_data[platform] = item
        if target in {"parse", "all"}:
            item["parse_proxy"] = proxy
        if target in {"download", "all"}:
            item["download_proxy"] = proxy
        _write_platform_config(self.path, data)

    def clear_proxy(self, platform: str, target: ProxyTarget = "all") -> bool:
        data = _read_toml(self.path)
        platform_data = data.get("platform", {})
        if not isinstance(platform_data, dict):
            return False
        item = platform_data.get(platform, {})
        if not isinstance(item, dict):
            return False
        changed = False
        if target in {"parse", "all"} and "parse_proxy" in item:
            del item["parse_proxy"]
            changed = True
        if target in {"download", "all"} and "download_proxy" in item:
            del item["download_proxy"]
            changed = True
        if not item:
            del platform_data[platform]
        if not platform_data:
            data.pop("platform", None)
        if changed:
            _write_platform_config(self.path, data)
        return changed


class FileCookieStore:
    def __init__(self, path: Path | None = None):
        self.path = default_cookie_path() if path is None else Path(path)

    def set(self, platform: str, cookie: str) -> None:
        data = _read_toml(self.path)
        cookies = data.setdefault("cookie", {})
        if not isinstance(cookies, dict):
            cookies = {}
            data["cookie"] = cookies
        cookies[platform] = cookie
        _write_cookie_config(self.path, data)
        _chmod_private(self.path)

    def get(self, platform: str) -> str | None:
        self._ensure_private_if_exists()
        data = _read_toml(self.path)
        cookies = data.get("cookie", {})
        if not isinstance(cookies, dict):
            return None
        return _optional_str(cookies.get(platform))

    def delete(self, platform: str) -> bool:
        data = _read_toml(self.path)
        cookies = data.get("cookie", {})
        if not isinstance(cookies, dict) or platform not in cookies:
            return False
        del cookies[platform]
        if not cookies:
            data.pop("cookie", None)
        _write_cookie_config(self.path, data)
        _chmod_private(self.path)
        return True

    def exists(self, platform: str) -> bool:
        return self.get(platform) is not None

    def _ensure_private_if_exists(self) -> None:
        if self.path.exists():
            _chmod_private(self.path)


class AutoCookieStore:
    def __init__(self, file_store: FileCookieStore | None = None):
        self.file_store = FileCookieStore() if file_store is None else file_store

    def set(self, platform: str, cookie: str) -> None:
        self.file_store.set(platform, cookie)

    def get(self, platform: str) -> str | None:
        return self.file_store.get(platform)

    def delete(self, platform: str) -> bool:
        return self.file_store.delete(platform)

    def exists(self, platform: str) -> bool:
        return self.file_store.exists(platform)


class CookiePrompt:
    def read(self, platform: str) -> str:
        cookie = getpass.getpass(f"请输入 {platform} Cookie: ")
        if not cookie.strip():
            raise ValueError("Cookie 不能为空")
        return cookie.strip()


def default_config_dir() -> Path:
    try:
        from platformdirs import user_config_dir
    except Exception:
        return _fallback_config_dir()
    return Path(user_config_dir("parsehub"))


def default_config_path() -> Path:
    return default_config_dir() / "config.toml"


def default_cookie_path() -> Path:
    return default_config_dir() / "cookies.toml"


def _fallback_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "parsehub"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "parsehub"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "parsehub"


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"配置文件无法解析: {path}") from e
    if not isinstance(data, dict):
        return {}
    return data


def _write_platform_config(path: Path, data: dict[str, Any]) -> None:
    platform_data = data.get("platform", {})
    lines: list[str] = []
    if isinstance(platform_data, dict):
        for platform, item in sorted(platform_data.items()):
            if not isinstance(item, dict):
                continue
            values = {k: v for k, v in item.items() if k in {"parse_proxy", "download_proxy"} and isinstance(v, str)}
            if not values:
                continue
            lines.append(f"[platform.{platform}]")
            for key in ("parse_proxy", "download_proxy"):
                if key in values:
                    lines.append(f"{key} = {_toml_string(values[key])}")
            lines.append("")
    _write_text(path, "\n".join(lines).rstrip() + ("\n" if lines else ""))


def _write_cookie_config(path: Path, data: dict[str, Any]) -> None:
    cookies = data.get("cookie", {})
    lines: list[str] = []
    if isinstance(cookies, dict) and cookies:
        lines.append("[cookie]")
        for platform, cookie in sorted(cookies.items()):
            if isinstance(cookie, str):
                lines.append(f"{platform} = {_toml_string(cookie)}")
    _write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
