from __future__ import annotations

import html
import re
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from ..utils.helpers import UA

_SHARE_URL = "https://weixin.qq.com/sph/{}"
_YUANBAO_API = "https://yuanbao.tencent.com/api/weixin/get_parse_result"
_FEED_API = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
_FEED_PAGE = "https://channels.weixin.qq.com/finder-preview/pages/feed"
_ID_RE = re.compile(
    r"(?:weixin\.qq\.com/sph/(\w+)|channels\.weixin\.qq\.com/finder-preview/pages/sph\?[^#]*?\bid=(\w+))"
)


@dataclass
class WXChannelsVideo:
    title: str
    author: str
    video_url: str
    thumb_url: str | None


class WXChannelsError(Exception):
    pass


class WXChannels:
    def __init__(self, cookie: str, proxy: str | None = None):
        self.cookie = cookie
        self.proxy = proxy

    async def parse(self, url: str) -> WXChannelsVideo:
        match = _ID_RE.search(url)
        if not match:
            raise WXChannelsError("不支持的微信视频号链接")
        share_id = match.group(1) or match.group(2)

        async with httpx.AsyncClient(proxy=self.proxy, timeout=30) as client:
            response = await client.post(
                _YUANBAO_API,
                json={"type": "video_channel_url", "url": _SHARE_URL.format(share_id), "scene": 1},
                headers={
                    "content-type": "application/json",
                    "User-Agent": UA,
                    "origin": "https://yuanbao.tencent.com",
                    "referer": "https://yuanbao.tencent.com/",
                    "cookie": self.cookie,
                },
            )
            if response.status_code == 401:
                raise WXChannelsError("Cookie 无效或已过期")
            response.raise_for_status()
            result = response.json()
            if error := result.get("error"):
                if str(error.get("code")) == "20000":
                    raise WXChannelsError("Cookie 无效或已过期")
                raise WXChannelsError(str(error.get("message") or error))
            if result.get("code") != 0:
                raise WXChannelsError(str(result.get("message") or "微信视频号解析失败"))

            data = result.get("data") or {}
            playable_url = data.get("playable_url") or ""
            if not data.get("wx_export_id") or not playable_url:
                raise WXChannelsError("视频不存在或已删除")

            playable_query = parse_qs(urlparse(playable_url).query)
            token = (playable_query.get("token") or [""])[0]
            export_id = (playable_query.get("eid") or [""])[0]
            if not token or not export_id:
                raise WXChannelsError("无法获取视频信息")

            rid = f"{int(time.time()):x}-{secrets.token_hex(4)}"
            response = await client.post(
                _FEED_API,
                params={"_rid": rid, "_pageUrl": _FEED_PAGE},
                json={"baseReq": {"generalToken": token}, "exportId": export_id},
                headers={
                    "content-type": "application/json",
                    "User-Agent": UA,
                    "origin": "https://channels.weixin.qq.com",
                    "referer": playable_url,
                },
            )
            response.raise_for_status()
            feed_result = response.json()

        feed_data = feed_result.get("data") or {}
        feed_error = feed_data.get("errMsg") or {}
        error_text = " ".join(
            _strip_html(str(feed_error.get(key) or "")) for key in ("title", "content")
        ).strip()
        if feed_result.get("errCode") != 0:
            message = feed_result.get("errMsg") or "微信视频号解析失败"
            raise WXChannelsError(str(message))
        if error_text:
            raise WXChannelsError(error_text)

        feed_info = feed_data.get("feedInfo") or {}
        video_url = (
            ((feed_info.get("h264VideoInfo") or {}).get("videoUrl"))
            or feed_info.get("videoUrl")
            or ((feed_info.get("h265VideoInfo") or {}).get("videoUrl"))
        )
        if not video_url:
            raise WXChannelsError("暂不支持该类型")

        author_info = feed_data.get("authorInfo") or {}
        return WXChannelsVideo(
            title=feed_info.get("description") or data.get("desc") or "",
            author=author_info.get("nickname") or data.get("author") or "",
            video_url=video_url,
            thumb_url=feed_info.get("coverUrl") or data.get("cover_url") or None,
        )


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", value)).strip()


__all__ = ["WXChannels", "WXChannelsError", "WXChannelsVideo"]
