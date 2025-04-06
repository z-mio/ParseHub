import re

import requests

from ..base.base import Parser
from ...types import (
    MultimediaParseResult,
    VideoParseResult,
    ImageParseResult,
    Video,
    Image,
    ParseError,
)
from instaloader import Post, InstaloaderContext, BadResponseException


class InstagramParser(Parser):
    __platform__ = "Instagram"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(www\.|)instagram\.com/(share/|.*)(p|reel)/.*"

    async def parse(
        self, url: str
    ) -> VideoParseResult | ImageParseResult | MultimediaParseResult | None:
        url = await self.get_raw_url(url)

        shortcode = self.get_short_code(url)
        if not shortcode:
            raise ValueError("Instagram帖子链接无效")
        try:
            post = Post.from_shortcode(MyInstaloaderContext(self.cfg.proxy), shortcode)
        except BadResponseException as e:
            match str(e):
                case "Fetching Post metadata failed.":
                    raise ParseError(
                        "受限视频无法解析: 你必须年满 18 周岁才能观看这个视频"
                    )
                case _:
                    raise ParseError("无法获取帖子内容")

        k = {"title": post.title, "desc": post.caption, "raw_url": url}
        match post.typename:
            case "GraphSidecar":
                media = [
                    Video(i.video_url, thumb_url=i.display_url)
                    if i.is_video
                    else Image(i.display_url)
                    for i in post.get_sidecar_nodes()
                ]
                return MultimediaParseResult(media=media, **k)
            case "GraphImage":
                return ImageParseResult(photo=[post.url], **k)
            case "GraphVideo":
                return VideoParseResult(
                    video=Video(post.video_url, thumb_url=post.url), **k
                )

    @staticmethod
    def get_short_code(url: str):
        url = url.removesuffix("/")
        shortcode = re.search(r"/(p|reel)/(.*)", url)
        return shortcode.group(2).split("/")[0] if shortcode else None


class MyInstaloaderContext(InstaloaderContext):
    """
    支持自定义代理
    """

    def __init__(self, proxy: str | None = None):
        self.proxy = {"http": proxy, "https": proxy}
        super().__init__()

    def get_anonymous_session(self) -> requests.Session:
        session = super().get_anonymous_session()
        if self.proxy:
            session.proxies = self.proxy
            session.trust_env = False
        return session

    def get_json(self, *args, **kwargs):
        session: requests.Session = kwargs.get("session")
        if self.proxy:
            session.proxies = self.proxy
            session.trust_env = False

        return super().get_json(*args, **kwargs)
