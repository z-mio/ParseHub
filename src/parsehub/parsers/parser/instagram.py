import re

from ..base.base import Parser
from ...types import (
    MultimediaParseResult,
    VideoParseResult,
    ImageParseResult,
    Video,
    Image,
)
from instaloader import Instaloader, Post


class InstagramParser(Parser):
    __platform__ = "Instagram"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(www\.|)instagram\.com/(share/|)(p|reel)/.*"

    async def parse(
        self, url: str
    ) -> VideoParseResult | ImageParseResult | MultimediaParseResult:
        url = await self.get_raw_url(url)

        ins = Instaloader()
        shortcode = self.get_short_code(url)
        if not shortcode:
            raise ValueError("Instagram帖子链接无效")
        post = Post.from_shortcode(ins.context, shortcode)
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
