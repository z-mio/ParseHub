import asyncio
import json
import re
from collections.abc import Coroutine
from typing import Any

from pydantic import SecretStr
from urlextract import URLExtract


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    coro.close()
    raise RuntimeError("sync API cannot be called from a running event loop; use async API instead")


_url_extractor = URLExtract()


def match_url(text: str) -> str:
    """从文本中提取url"""
    if not text:
        return ""
    text = re.sub(r"(https?://)", r" \1", text)  # 协议前面增加空格, 方便提取
    url = _url_extractor.find_urls(text, only_unique=True)
    return url[0] if url else ""


class SecretCookie:
    def __init__(self, cookie: str | dict[str, Any] | None = None) -> None:
        self._cookie = self.normalize_cookie(cookie)

    def __bool__(self) -> bool:
        return bool(self._cookie)

    def __str__(self) -> str:
        if self._cookie is None:
            return ""
        return "; ".join([f"{k}={v}" for k, v in self._cookie.items()])

    def get_value(self) -> dict[str, str] | None:
        if self._cookie is None:
            return None
        return {key: value.get_secret_value() for key, value in self._cookie.items()}

    @staticmethod
    def normalize_cookie(v: str | dict[str, Any] | None) -> dict[str, SecretStr] | None:
        if v is None:
            return v
        if isinstance(v, dict):
            return {str(k).strip(): SecretStr("" if v is None else str(v).strip()) for k, v in v.items()}
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None

            if s.startswith("{") and s.endswith("}"):
                try:
                    data = json.loads(s)
                except Exception as e:
                    raise ValueError(f"cookie JSON解析失败: {e}") from e
                if not isinstance(data, dict):
                    raise ValueError("cookie JSON必须是对象类型")
                return {str(k).strip(): SecretStr("" if v is None else str(v).strip()) for k, v in data.items()}

            if s.lower().startswith("cookie:"):
                s = s[7:].strip()

            parts = [p.strip() for p in s.split(";") if p.strip()]
            result: dict[str, SecretStr] = {}
            for p in parts:
                if "=" not in p:
                    key = p.strip()
                    if key:
                        result[key] = SecretStr("")
                    continue
                k, val = p.split("=", 1)
                result[k.strip()] = SecretStr(val.strip())
            return result or None

        raise ValueError("cookie 必须是字符串、字典、JSON 或 None")
