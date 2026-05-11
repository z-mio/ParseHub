import asyncio
import html
import json
import re
from typing import Any, NamedTuple
from urllib.parse import urlencode, urlparse

import httpx

from ..config import GlobalConfig

TIKTOK_APP_FEED = "https://api22-normal-c-alisg.tiktokv.com/aweme/v1/feed/"

FACEBOOK_EXTERNAL_HIT_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
UNIVERSAL_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(?P<json>.*?)</script>',
    re.DOTALL,
)

TIKTOK_HEADERS = {
    "User-Agent": GlobalConfig.ua,
    "Referer": "https://www.tiktok.com/",
    "x-ladon": "Hello From Evil0ctal!",
}

TIKTOK_WEB_HEADERS = {
    "User-Agent": GlobalConfig.ua,
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
        self.headers = dict(TIKTOK_HEADERS)
        if user_agent:
            self.headers["User-Agent"] = user_agent
        self.cookies = httpx.Cookies()
        for key, value in (cookie or {}).items():
            self.cookies.set(str(key), "" if value is None else str(value))
        self.proxy = proxy
        self.max_retries = max_retries
        self.timeout = timeout

    async def parse(self, url: str) -> dict:
        item_ref = None
        primary_error: Exception | None = None

        try:
            resolved_url = await self.resolve_url(url)
            item_ref = self.extract_item_ref_from_url(resolved_url)
            if not item_ref:
                raise ValueError(f"无法从链接中提取作品 ID: {resolved_url}")
            return await self.fetch_one_video(item_ref.aweme_id)
        except Exception as exc:
            primary_error = exc

        if item_ref and item_ref.media_type == "photo":
            raise RuntimeError(f"获取 TikTok 图文作品失败: {primary_error}") from primary_error

        try:
            return await self.fetch_video_from_web(url, expected_aweme_id=item_ref.aweme_id if item_ref else None)
        except Exception as web_error:
            raise RuntimeError(f"获取 TikTok 作品失败: feed={primary_error}; web={web_error}") from web_error

    def _client(self, *, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=headers or self.headers,
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

    async def resolve_web_url(self, url_or_text: str) -> str:
        url = self.extract_url(url_or_text)
        if self.extract_item_ref_from_url(url):
            return url

        headers = dict(TIKTOK_WEB_HEADERS)
        headers["User-Agent"] = FACEBOOK_EXTERNAL_HIT_UA
        async with self._client(headers=headers) as client:
            response = await client.head(url)
            if response.status_code >= 400:
                response = await client.get(url)
            response.raise_for_status()
            return str(response.url)

    async def fetch_one_video(self, aweme_id: str) -> dict[str, Any]:
        params = {
            "iid": 7318518857994389254,
            "device_id": 7318517321748022790,
            "channel": "googleplay",
            "app_name": "musical_ly",
            "version_code": "300904",
            "device_platform": "android",
            "device_type": "SM-ASUS_Z01QD",
            "os_version": "9",
            "aweme_id": aweme_id,
        }
        endpoint = f"{TIKTOK_APP_FEED}?{urlencode(params)}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                async with self._client() as client:
                    response = await client.get(endpoint)
                    response.raise_for_status()
                    payload = response.json()

                aweme_list = payload.get("aweme_list") or []
                for item in aweme_list:
                    if str(item.get("aweme_id")) == str(aweme_id):
                        return item

                if aweme_list:
                    first_id = aweme_list[0].get("aweme_id")
                    raise RuntimeError(f"返回作品 ID 不匹配: expected={aweme_id}, got={first_id}")

                status_msg = payload.get("status_msg") or payload.get("statusMessage") or payload
                raise RuntimeError(f"接口未返回 aweme_list: {status_msg}")
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(1)

        raise RuntimeError(f"获取 TikTok 作品失败: {last_error}")

    async def fetch_video_from_web(self, url_or_text: str, expected_aweme_id: str | None = None) -> dict[str, Any]:
        url = await self.resolve_web_url(url_or_text)
        item_ref = self.extract_item_ref_from_url(url)
        if not item_ref:
            raise ValueError(f"无法从链接中提取作品 ID: {url}")
        if item_ref.media_type == "photo":
            raise ValueError("TikTok 图文作品不支持 Web hydration fallback")

        webpage = await self.download_webpage(url)
        universal_data = self._search_universal_data(webpage)
        if not universal_data:
            raise RuntimeError("无法从页面提取 __UNIVERSAL_DATA_FOR_REHYDRATION__")

        item = self._extract_web_item(universal_data)
        item_id = str(item.get("aweme_id") or item.get("id") or "")
        expected_id = str(expected_aweme_id or item_ref.aweme_id)
        if item_id and item_id != expected_id:
            raise RuntimeError(f"返回作品 ID 不匹配: expected={expected_id}, got={item_id}")
        if item_id and not item.get("aweme_id"):
            item["aweme_id"] = item_id
        return item

    async def download_webpage(self, url: str) -> str:
        async with self._client(headers=TIKTOK_WEB_HEADERS) as client:
            last_webpage = ""
            for attempt in range(self.max_retries):
                response = await client.get(url)
                if urlparse(str(response.url)).path == "/login":
                    raise RuntimeError("TikTok 要求登录才能访问这个内容")
                response.raise_for_status()
                webpage = response.text
                if self._search_universal_data(webpage):
                    return webpage
                last_webpage = webpage
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(1)
            return last_webpage

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
        return data.get("__DEFAULT_SCOPE__") or {}

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
            return item
        if status in (10216, 10222):
            raise RuntimeError("这个 TikTok 内容需要登录或无权访问")
        if status == 10204:
            raise RuntimeError("当前 IP 被 TikTok 阻止访问这个内容")
        status_msg = detail.get("statusMsg") or detail.get("statusMessage") or status
        raise RuntimeError(f"页面中没有作品详情，status={status_msg}")
