import asyncio
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import GlobalConfig

TIKTOK_APP_FEED = "https://api22-normal-c-alisg.tiktokv.com/aweme/v1/feed/"

TIKTOK_HEADERS = {
    "User-Agent": GlobalConfig.ua,
    "Referer": "https://www.tiktok.com/",
    "x-ladon": "Hello From Evil0ctal!",
}


def _proxy_kwargs(proxy: str | None) -> dict:
    if not proxy:
        return {}
    try:
        ver = tuple(int(x) for x in httpx.__version__.split(".")[:2])
        if ver >= (0, 28):
            return {"proxy": proxy}
    except Exception:
        pass
    return {"proxies": proxy}


class TikTokWebCrawler:
    _ITEM = re.compile(r"/(?:video|photo)/(\d+)")
    _URL = re.compile(r"https?://\S+")

    def __init__(
        self,
        cookie: str = None,
        proxy: str = None,
        user_agent: str = None,
        max_retries: int = 3,
        timeout: int = 15,
    ):
        self.headers = dict(TIKTOK_HEADERS)
        if user_agent:
            self.headers["User-Agent"] = user_agent
        if cookie:
            self.headers["Cookie"] = cookie

        self.proxy = proxy
        self.max_retries = max_retries
        self.timeout = timeout

    async def parse(self, url: str) -> dict:
        aweme_id = await self.get_aweme_id(url)
        return await self.fetch_one_video(aweme_id)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
            **_proxy_kwargs(self.proxy),
        )

    @classmethod
    def extract_url(cls, text: str) -> str:
        match = cls._URL.search(text)
        if not match:
            raise ValueError("未找到 TikTok URL")
        return match.group(0).rstrip(".,;，。；'\")]}）】>」』")

    @classmethod
    def extract_aweme_id_from_url(cls, url: str) -> str | None:
        match = cls._ITEM.search(url)
        return match.group(1) if match else None

    async def resolve_url(self, url_or_text: str) -> str:
        url = self.extract_url(url_or_text)
        if self.extract_aweme_id_from_url(url):
            return url

        async with self._client() as client:
            response = await client.get(url)
            response.raise_for_status()
            resolved = str(response.url)

        if "notfound" in resolved.lower():
            raise ValueError("TikTok 页面不可用，可能是地区、代理或链接问题")
        return resolved

    async def get_aweme_id(self, url_or_text: str) -> str:
        resolved_url = await self.resolve_url(url_or_text)
        aweme_id = self.extract_aweme_id_from_url(resolved_url)
        if not aweme_id:
            raise ValueError(f"无法从链接中提取作品 ID: {resolved_url}")
        return aweme_id

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
