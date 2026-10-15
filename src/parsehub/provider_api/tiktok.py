import asyncio
import base64
import hashlib
import html
import json
import re
from typing import Any, NamedTuple, cast
from urllib.parse import urlparse

import httpx

from ..utils.helpers import UA

TIKTOK_ITEM_PAGE = "https://www.tiktok.com/@_/video/{aweme_id}"

UNIVERSAL_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(?P<json>.*?)</script>',
    re.DOTALL,
)

TIKTOK_WEB_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tiktok.com/",
}


class TikTokItemRef(NamedTuple):
    media_type: str
    aweme_id: str


class TikTokWebCrawler:
    _ITEM = re.compile(r"/(?P<media_type>video|photo)/(?P<aweme_id>\d+)")
    _URL = re.compile(r"https?://\S+")

    def __init__(
        self,
        cookie: dict | None = None,
        proxy: str | None = None,
        user_agent: str | None = None,
        max_retries: int = 3,
        timeout: int = 15,
    ):
        self.headers = dict(TIKTOK_WEB_HEADERS)
        if user_agent:
            self.headers["User-Agent"] = user_agent
        self.cookies = httpx.Cookies()
        for key, value in (cookie or {}).items():
            self.cookies.set(str(key), "" if value is None else str(value))
        self.proxy = proxy
        self.max_retries = max_retries
        self.timeout = timeout

    async def parse(self, url: str) -> dict[str, Any]:
        resolved_url = await self.resolve_url(url)
        item_ref = self.extract_item_ref_from_url(resolved_url)
        if not item_ref:
            raise ValueError(f"无法从链接中提取作品 ID: {resolved_url}")
        return await self.fetch_item(item_ref.aweme_id)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
            proxy=self.proxy,
            cookies=self.cookies,
        )

    @classmethod
    def extract_url(cls, text: str) -> str:
        text = html.unescape(text.strip())
        markdown_match = re.search(r"]\((https?://[^)]+)\)", text)
        if markdown_match:
            return markdown_match.group(1).rstrip(".,;，。；'\")]}）】>」』")
        match = cls._URL.search(text)
        if not match:
            raise ValueError("未找到 TikTok URL")
        return match.group(0).rstrip(".,;，。；'\")]}）】>」』")

    @classmethod
    def extract_item_ref_from_url(cls, url: str) -> TikTokItemRef | None:
        match = cls._ITEM.search(url)
        if not match:
            return None
        return TikTokItemRef(match.group("media_type"), match.group("aweme_id"))

    async def resolve_url(self, url_or_text: str) -> str:
        url = self.extract_url(url_or_text)
        if self.extract_item_ref_from_url(url):
            return url

        async with self._client() as client:
            response = await client.get(url)
            response.raise_for_status()
            resolved = str(response.url)

        if "notfound" in resolved.lower():
            raise ValueError("TikTok 页面不可用，可能是地区、代理或链接问题")
        return resolved

    async def fetch_item(self, aweme_id: str) -> dict[str, Any]:
        # 图文也要请求 /video/ 页面, /photo/ 页面里没有 webapp.video-detail
        webpage = await self.download_webpage(TIKTOK_ITEM_PAGE.format(aweme_id=aweme_id))
        universal_data = self._search_universal_data(webpage)
        if not universal_data:
            raise RuntimeError("无法从页面提取 __UNIVERSAL_DATA_FOR_REHYDRATION__")

        item = self._extract_web_item(universal_data)
        item_id = str(item.get("aweme_id") or item.get("id") or "")
        if item_id and item_id != aweme_id:
            raise RuntimeError(f"返回作品 ID 不匹配: expected={aweme_id}, got={item_id}")
        if item_id and not item.get("aweme_id"):
            item["aweme_id"] = item_id
        return item

    async def download_webpage(self, url: str) -> str:
        async with self._client() as client:
            webpage = ""
            for attempt in range(self.max_retries):
                response = await client.get(url)
                if urlparse(str(response.url)).path == "/login":
                    raise RuntimeError("TikTok 要求登录才能访问这个内容")
                response.raise_for_status()
                webpage = response.text
                if self._search_universal_data(webpage):
                    return webpage
                if self._solve_challenge(client, webpage):
                    continue
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(1)
            return webpage

    @staticmethod
    def _html_class(webpage: str, element_id: str) -> str | None:
        match = re.search(rf'<[^>]+\bid="{element_id}"[^>]*>', webpage)
        if not match:
            return None
        class_match = re.search(r'\bclass="([^"]*)"', match.group(0))
        return class_match.group(1) if class_match else None

    @classmethod
    def _solve_challenge(cls, client: httpx.AsyncClient, webpage: str) -> bool:
        """解 WAF 的 sha256 计算挑战并写入 cookie, 做法同 yt-dlp"""
        encoded = cls._html_class(webpage, "cs")
        cookie_name = cls._html_class(webpage, "wci")
        if not encoded or not cookie_name:
            return False
        try:
            challenge = json.loads(base64.b64decode(f"{encoded}==="))
            expected_digest = base64.b64decode(challenge["v"]["c"])
            base_hash = hashlib.sha256(base64.b64decode(challenge["v"]["a"]))
        except (ValueError, KeyError, TypeError):
            return False

        for i in range(1_000_001):
            number = str(i).encode()
            test_hash = base_hash.copy()
            test_hash.update(number)
            if test_hash.digest() == expected_digest:
                challenge["d"] = base64.b64encode(number).decode()
                break
        else:
            return False

        cookie_value = base64.b64encode(json.dumps(challenge, separators=(",", ":")).encode()).decode()
        client.cookies.set(cookie_name, cookie_value, domain=".tiktok.com")
        rci_name = cls._html_class(webpage, "rci")
        rci_value = cls._html_class(webpage, "rs")
        if rci_name and rci_value:
            client.cookies.set(rci_name, rci_value, domain=".tiktok.com")
        return True

    @staticmethod
    def _search_universal_data(webpage: str) -> dict[str, Any]:
        match = UNIVERSAL_DATA_RE.search(webpage)
        if not match:
            return {}
        raw = html.unescape(match.group("json")).strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return cast(dict[str, Any], data.get("__DEFAULT_SCOPE__") or {})

    @staticmethod
    def _extract_web_item(universal_data: dict[str, Any]) -> dict[str, Any]:
        detail = universal_data.get("webapp.video-detail") or {}
        status = detail.get("statusCode") or 0
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = 0
        item = ((detail.get("itemInfo") or {}).get("itemStruct")) or {}
        if item:
            return cast(dict[str, Any], item)
        if status in (10216, 10222):
            raise RuntimeError("这个 TikTok 内容需要登录或无权访问")
        if status == 10204:
            raise RuntimeError("当前 IP 被 TikTok 阻止访问这个内容")
        status_msg = detail.get("statusMsg") or detail.get("statusMessage") or status
        raise RuntimeError(f"页面中没有作品详情，status={status_msg}")
