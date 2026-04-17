import asyncio
import json
import re

import httpx

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

TIKTOK_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Referer": "https://www.tiktok.com/",
}

UNIVERSAL_DATA_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def parse_cookie_string(cookie_str: str) -> dict:
    result = {}
    if not cookie_str:
        return result
    for piece in cookie_str.split(";"):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        k, _, v = piece.partition("=")
        if k.strip():
            result[k.strip()] = v.strip()
    return result


def _proxy_kwargs(proxy):
    if not proxy:
        return {}
    try:
        ver = tuple(int(x) for x in httpx.__version__.split(".")[:2])
        if ver >= (0, 28):
            return {"proxy": proxy}
    except Exception:
        pass
    return {"proxies": proxy}


def extract_item_from_html(html: str, item_id: str) -> dict | None:
    m = UNIVERSAL_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    scope = data.get("__DEFAULT_SCOPE__", {})
    vd = scope.get("webapp.video-detail") or {}
    item_info = vd.get("itemInfo") or {}
    item = item_info.get("itemStruct") or {}
    if item.get("id") == item_id:
        return {"itemInfo": {"itemStruct": item}, "statusCode": 0, "status_code": 0}

    ud = scope.get("webapp.user-detail") or {}
    for it in ud.get("itemList") or []:
        if it.get("id") == item_id:
            return {"itemInfo": {"itemStruct": it}, "statusCode": 0, "status_code": 0}

    if item:
        return {"itemInfo": {"itemStruct": item}, "statusCode": 0, "status_code": 0}
    return None


class TikTokWebCrawler:
    _VIDEO = re.compile(r"video/(\d+)")
    _PHOTO = re.compile(r"photo/(\d+)")

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

        self.cookies = httpx.Cookies()
        if cookie:
            for k, v in parse_cookie_string(cookie).items():
                self.cookies.set(k, v, domain=".tiktok.com", path="/")

        self.proxy = proxy
        self.max_retries = max_retries
        self.timeout = timeout

    async def parse(self, url: str) -> dict:
        item_id, canonical_url = await self._normalize_url(url)

        try:
            data = await self._fetch_via_html(canonical_url, item_id)
            if data:
                return data
        except Exception:
            pass

        raise RuntimeError("HTML parsing failed. Possible causes: IP region restriction or video deleted.")

    async def _normalize_url(self, url: str) -> tuple:
        if "tiktok" in url and "@" in url:
            m = self._VIDEO.search(url) or self._PHOTO.search(url)
            if m:
                return m.group(1), url

        async with httpx.AsyncClient(timeout=self.timeout, **_proxy_kwargs(self.proxy)) as c:
            r = await c.get(url, follow_redirects=True, headers=self.headers)
            final = str(r.url)
            m = self._VIDEO.search(final) or self._PHOTO.search(final)
            if not m:
                raise ValueError(f"aweme_id not found: {final}")
            return m.group(1), final

    async def _fetch_via_html(self, canonical_url: str, item_id: str) -> dict | None:
        async with httpx.AsyncClient(
            headers={
                **self.headers,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
            cookies=self.cookies,
            timeout=httpx.Timeout(self.timeout),
            **_proxy_kwargs(self.proxy),
        ) as c:
            r = await c.get(canonical_url, follow_redirects=True)
            if r.status_code != 200 or not r.text:
                return None

            return extract_item_from_html(r.text, item_id)


async def main():
    cookie = ""
    crawler = TikTokWebCrawler(
        cookie=cookie,
    )
    result = await crawler.parse("https://www.tiktok.com/@samisizzle/photo/7147496455962545413?_r=1&_t=ZS-95c2pN3J61p")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
