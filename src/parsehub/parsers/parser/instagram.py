import re

from ...provider_api.instagram import (
    InstagramAPI,
    InstagramAPIError,
    InstagramMediaType,
    InstagramPost,
    InstagramRestrictedError,
)
from ...types import (
    ContentUnavailableError,
    ImageParseResult,
    ImageRef,
    MultimediaParseResult,
    ParseError,
    Platform,
    VideoParseResult,
    VideoRef,
)
from ...utils.helpers import SecretCookie
from ..base.base import BaseParser, FallbackStage


class InstagramParser(BaseParser):
    __platform__ = Platform.INSTAGRAM
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(www\.|)instagram\.com/(p|reel|reels|share|.*/p|.*/reel)/.*"
    __redirect_keywords__ = ["share"]

    async def _do_parse(self, raw_url: str) -> VideoParseResult | ImageParseResult | MultimediaParseResult:
        shortcode = self.get_short_code(raw_url)
        if not shortcode:
            raise ValueError("Instagram帖子链接无效")

        post = await self._parse(shortcode)

        width, height = post.width, post.height

        match post.typename:
            case InstagramMediaType.SIDECAR:
                media = [
                    VideoRef(url=i.video_url, thumb_url=i.display_url, width=i.width, height=i.height)
                    if i.is_video and i.video_url
                    else ImageRef(url=i.display_url, width=i.width, height=i.height)
                    for i in post.get_sidecar_nodes()
                ]
                return MultimediaParseResult(media=media, title=post.title, content=post.caption)
            case InstagramMediaType.IMAGE:
                return ImageParseResult(
                    photo=[ImageRef(url=post.url, width=width, height=height)], title=post.title, content=post.caption
                )
            case InstagramMediaType.VIDEO:
                return VideoParseResult(
                    video=VideoRef(
                        url=post.video_url or post.url,
                        thumb_url=post.url,
                        duration=int(post.video_duration or 0),
                        width=width,
                        height=height,
                    ),
                    title=post.title,
                    content=post.caption,
                )
            case _:
                raise ParseError("不支持的类型")

    async def _parse(self, shortcode: str) -> InstagramPost:
        stages: list[FallbackStage[InstagramPost]] = [FallbackStage("匿名", lambda: self._fetch(shortcode))]
        if self.cookie.get_value():
            stages.append(
                FallbackStage("cookie", lambda: self._fetch(shortcode, self.cookie), cookie=True)
            )
        return await self._fallback(
            *stages, stop=lambda e: not isinstance(e.__cause__, InstagramRestrictedError)
        )

    async def _fetch(self, shortcode: str, cookie: SecretCookie | None = None) -> InstagramPost:
        api = InstagramAPI(proxy=self.proxy, cookie=cookie.get_value() if cookie else None, timeout=30)
        try:
            return await api.get_post(shortcode)
        except ContentUnavailableError:
            raise
        except Exception as e:
            if isinstance(e, InstagramRestrictedError):
                text = str(e)
            elif isinstance(e, InstagramAPIError):
                text = f"无法获取帖子内容: {e}"
            else:
                text = f"无法获取帖子内容(可能为私人内容): {e}"
            raise ParseError(text) from e

    @staticmethod
    def get_short_code(url: str) -> str | None:
        url = url.removesuffix("/")
        shortcode = re.search(r"/(p|reel|reels|share|.*/p|.*/reel)/(.*)", url)
        return shortcode.group(2).split("/")[0] if shortcode else None


__all__ = ["InstagramParser"]
