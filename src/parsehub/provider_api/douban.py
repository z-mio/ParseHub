import re
from dataclasses import dataclass, field
from typing import Any, cast

import httpx
from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter

TOPIC_API = "https://m.douban.com/rexxar/api/v2/group/topic/{}"
IMAGE_REFERER = "https://www.douban.com/"
"""豆瓣图床有防盗链, 下载图片时必须带上 Referer"""

TOPIC_URL_RE = r"douban\.com/(?:group/)?topic/(\d+)"
"""/group/topic/<id> 与 /topic/<id> 共用同一套 ID. 锚定域名避免误匹配 /gallery/topic/<id> (另一套 ID)"""

# rexxar 是移动版网页的内部接口, 无 UA 时返回 418
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class Douban:
    def __init__(self, proxy: str | None = None, cookie: dict[str, str] | None = None):
        self.proxy = proxy
        self.cookie = cookie

    async def parse(self, url: str) -> "DoubanTopic":
        return DoubanTopic.parse(await self.fetch_topic_data(url))

    @staticmethod
    def get_topic_id(url: str) -> str:
        if match := re.search(TOPIC_URL_RE, url):
            return match.group(1)
        raise DoubanError("暂不支持该豆瓣链接, 目前仅支持小组话题")

    async def fetch_topic_data(self, url: str) -> dict[str, Any]:
        headers = {"User-Agent": MOBILE_UA, "Referer": "https://m.douban.com/"}
        async with httpx.AsyncClient(proxy=self.proxy, cookies=self.cookie, timeout=30) as cli:
            result = await cli.get(TOPIC_API.format(self.get_topic_id(url)), headers=headers)

        if result.status_code != 200:
            fallback = f"获取话题内容失败: HTTP {result.status_code}"
            try:
                error = result.json()
            except Exception as e:
                raise DoubanError(fallback) from e
            # 缺少 localized_message 时 msg 只是英文错误码 (如 need_permission), 需补中文上下文
            if localized := error.get("localized_message"):
                raise DoubanError(localized)
            if msg := error.get("msg"):
                raise DoubanError(f"获取话题内容失败: {msg}")
            raise DoubanError(fallback)

        return cast(dict[str, Any], result.json())


@dataclass
class DoubanVideo:
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0
    duration: int = 0


@dataclass
class DoubanPhoto:
    url: str
    ext: str = "jpg"
    thumb_url: str | None = None
    width: int = 0
    height: int = 0
    is_animated: bool = False


@dataclass
class DoubanTopic:
    title: str
    markdown_content: str
    text_content: str
    video: DoubanVideo | None = None
    photos: list[DoubanPhoto] = field(default_factory=list)

    @classmethod
    def parse(cls, data: dict) -> "DoubanTopic":
        content = data.get("content") or ""
        markdown_content = MarkdownConverter(heading_style="ATX").convert(content).strip() if content else ""
        text_content = "".join(BeautifulSoup(markdown(markdown_content), "lxml").find_all(string=True)).strip()

        video_info = data.get("video_info") or {}
        return cls(
            title=data.get("title") or "",
            markdown_content=markdown_content,
            text_content=text_content,
            video=parse_video(video_info) if video_info else None,
            photos=[p for photo in data.get("photos") or [] if (p := parse_photo(photo))],
        )


def parse_photo(photo: dict) -> DoubanPhoto | None:
    image = photo.get("image") or {}
    large = image.get("large") or {}
    normal = image.get("normal") or {}

    # 动图的 large 是体积极大的原始 GIF, 豆瓣同时提供了等效的 mp4
    if image.get("is_animated") and (video := image.get("video")) and video.get("url"):
        return DoubanPhoto(
            url=video["url"],
            ext="mp4",
            thumb_url=normal.get("url"),
            width=video.get("width") or 0,
            height=video.get("height") or 0,
            is_animated=True,
        )

    source = large or normal
    if not (url := source.get("url")):
        return None
    thumb_url = normal.get("url")
    return DoubanPhoto(
        url=url,
        thumb_url=thumb_url if thumb_url != url else None,
        width=source.get("width") or 0,
        height=source.get("height") or 0,
    )


def parse_video(video_info: dict) -> DoubanVideo | None:
    if not (url := video_info.get("video_url")):
        return None
    return DoubanVideo(
        url=url,
        thumb_url=video_info.get("cover_url"),
        width=video_info.get("video_width") or 0,
        height=video_info.get("video_height") or 0,
        duration=parse_duration(video_info.get("duration")),
    )


def parse_duration(duration: Any) -> int:
    """把 ``HH:MM:SS`` / ``MM:SS`` 形式的时长转换为秒"""
    if isinstance(duration, int):
        return duration
    if not isinstance(duration, str):
        return 0
    seconds = 0
    for part in duration.split(":"):
        if not part.isdigit():
            return 0
        seconds = seconds * 60 + int(part)
    return seconds


class DoubanError(Exception):
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)
