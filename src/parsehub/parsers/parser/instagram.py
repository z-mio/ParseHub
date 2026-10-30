import re

from loguru import logger

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
from ..base.ytdlp import YtParser, YtVideoParseResult


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

        match post.type:
            case InstagramMediaType.SIDECAR:
                media = [
                    VideoRef(
                        url=item.video_url,
                        thumb_url=item.display_url,
                        duration=int(item.duration),
                        width=item.width,
                        height=item.height,
                    )
                    if item.is_video
                    else ImageRef(url=item.display_url, width=item.width, height=item.height)
                    for item in post.media
                ]
                return MultimediaParseResult(media=media, title=post.title, content=post.caption)
            case InstagramMediaType.IMAGE:
                item = post.media[0]
                return ImageParseResult(
                    photo=[ImageRef(url=item.display_url, width=item.width, height=item.height)],
                    title=post.title,
                    content=post.caption,
                )
            case InstagramMediaType.VIDEO:
                item = post.media[0]
                try:
                    info = await InstagramYtParse(proxy=self.proxy)._parse(f"https://www.instagram.com/p/{shortcode}/")
                except ParseError as e:
                    logger.warning(f"Instagram yt-dlp 解析失败, 使用直链视频: {e}")
                else:
                    return YtVideoParseResult(
                        dl=info,
                        title=post.title,
                        content=post.caption,
                        video=VideoRef(
                            url=info.url,
                            thumb_url=item.display_url or info.thumbnail,
                            width=info.width,
                            height=info.height,
                            duration=int(info.duration or item.duration),
                        ),
                    )
                if not item.video_url:
                    raise ParseError("未获取到视频地址")
                return VideoParseResult(
                    video=VideoRef(
                        url=item.video_url,
                        thumb_url=item.display_url,
                        duration=int(item.duration),
                        width=item.width,
                        height=item.height,
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
        except InstagramRestrictedError as e:
            raise ParseError(str(e)) from e
        except InstagramAPIError as e:
            raise ParseError(f"无法获取帖子内容: {e}") from e

    @staticmethod
    def get_short_code(url: str) -> str | None:
        url = url.removesuffix("/")
        shortcode = re.search(r"/(p|reel|reels|share|.*/p|.*/reel)/(.*)", url)
        return shortcode.group(2).split("/")[0] if shortcode else None


class InstagramYtParse(YtParser, register=False):
    pass


__all__ = ["InstagramParser"]
