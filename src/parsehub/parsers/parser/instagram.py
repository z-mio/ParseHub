import asyncio
import re

from instaloader import BadResponseException

from ...provider_api.instagram import MyInstaloaderContext, MyPost
from ...types import ImageParseResult, ImageRef, MultimediaParseResult, ParseError, Platform, VideoParseResult, VideoRef
from ...utils.util import cookie_ellipsis
from ..base.base import BaseParser


class InstagramParser(BaseParser):
    __platform__ = Platform.INSTAGRAM
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(www\.|)instagram\.com/(p|reel|share|.*/p|.*/reel)/.*"
    __redirect_keywords__ = ["share"]

    async def _do_parse(self, raw_url: str) -> VideoParseResult | ImageParseResult | MultimediaParseResult | None:
        shortcode = self.get_short_code(raw_url)
        if not shortcode:
            raise ValueError("Instagram帖子链接无效")

        post = await self._parse(raw_url, shortcode)

        try:
            dimensions: dict = post._field("dimensions")
        except KeyError:
            dimensions = {}
        width, height = dimensions.get("width", 0) or 0, dimensions.get("height", 0) or 0

        k = {"title": post.title, "content": post.caption, "raw_url": raw_url}
        match post.typename:
            case "GraphSidecar":
                media = [
                    VideoRef(url=i.video_url, thumb_url=i.display_url, width=i.width, height=i.height)
                    if i.is_video
                    else ImageRef(url=i.display_url, width=i.width, height=i.height)
                    for i in post.get_sidecar_nodes()
                ]
                return MultimediaParseResult(media=media, **k)
            case "GraphImage":
                return ImageParseResult(photo=[ImageRef(url=post.url, width=width, height=height)], **k)
            case "GraphVideo":
                return VideoParseResult(
                    video=VideoRef(
                        url=post.video_url,
                        thumb_url=post.url,
                        duration=int(post.video_duration),
                        width=width,
                        height=height,
                    ),
                    **k,
                )
            case _:
                raise ParseError("不支持的类型")

    async def _parse(self, url, shortcode, cookie=None) -> MyPost:
        try:
            post = await asyncio.wait_for(
                asyncio.to_thread(
                    MyPost.from_shortcode,
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
        shortcode = re.search(r"/(share|p|reel|.*/p|.*/reel)/(.*)", url)
        return shortcode.group(2).split("/")[0] if shortcode else None


__all__ = ["InstagramParser"]
