import asyncio
import re

import requests
from instaloader import BadResponseException, InstaloaderContext, Post

from ...types import (
    Image,
    ImageParseResult,
    MultimediaParseResult,
    ParseError,
    Video,
    VideoParseResult,
)
from ...utiles.utile import cookie_ellipsis
from ..base.base import BaseParser


class InstagramParser(BaseParser):
    __platform_id__ = "instagram"
    __platform__ = "Instagram"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(www\.|)instagram\.com/(p|reel|share|.*/p)/.*"
    __redirect_keywords__ = ["share"]

    async def parse(self, url: str) -> VideoParseResult | ImageParseResult | MultimediaParseResult | None:
        url = await self.get_raw_url(url)

        shortcode = self.get_short_code(url)
        if not shortcode:
            raise ValueError("Instagram帖子链接无效")

        post = await self._parse(url, shortcode)

        k = {"title": post.title, "desc": post.caption, "raw_url": url}
        match post.typename:
            case "GraphSidecar":
                media = [
                    Video(i.video_url, thumb_url=i.display_url) if i.is_video else Image(i.display_url)
                    for i in post.get_sidecar_nodes()
                ]
                return MultimediaParseResult(media=media, **k)
            case "GraphImage":
                return ImageParseResult(photo=[post.url], **k)
            case "GraphVideo":
                return VideoParseResult(video=Video(post.video_url, thumb_url=post.url), **k)

    async def _parse(self, url, shortcode, cookie=None):
        try:
            post = await asyncio.wait_for(
                asyncio.to_thread(
                    Post.from_shortcode,
                    MyInstaloaderContext(self.cfg.proxy, cookie),
                    shortcode,
                ),
                30,
            )
        except TimeoutError as e:
            raise ParseError("解析超时") from e
        except BadResponseException as e:
            match str(e):
                case "Fetching Post metadata failed.":
                    if self.cfg.cookie and cookie is None:
                        return await self._parse(url, shortcode, self.cfg.cookie)
                    else:
                        raise ParseError("受限视频无法解析: 你必须年满 18 周岁才能观看这个视频") from e
                case _:
                    raise ParseError("无法获取帖子内容") from e
        except Exception as e:
            if cookie:
                text = f"Instagram 账号可能已被封禁\n\n使用的Cookie: {cookie_ellipsis(cookie)}"
            else:
                text = e
            raise ParseError(f"无法获取帖子内容: {text}") from e
        else:
            return post

    @staticmethod
    def get_short_code(url: str):
        url = url.removesuffix("/")
        shortcode = re.search(r"/(share|p|reel)/(.*)", url)
        return shortcode.group(2).split("/")[0] if shortcode else None


class MyInstaloaderContext(InstaloaderContext):
    """
    支持自定义代理
    """

    def __init__(self, proxy: str | None = None, cookie: dict = None):
        self.proxy = {"http": proxy, "https": proxy}
        self.cookie = cookie
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
        if self.cookie:
            session.cookies.update(self.cookie)

        return super().get_json(*args, **kwargs)


__all__ = ["InstagramParser"]
