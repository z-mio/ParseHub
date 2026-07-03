import re

from ...provider_api.instagram import InstagramAPI, InstagramAPIError, InstagramMediaType, InstagramPost
from ...types import ImageParseResult, ImageRef, MultimediaParseResult, ParseError, Platform, VideoParseResult, VideoRef
from ...utils.helpers import SecretCookie
from ..base.base import BaseParser


class InstagramParser(BaseParser):
    __platform__ = Platform.INSTAGRAM
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(www\.|)instagram\.com/(p|reel|reels|share|.*/p|.*/reel)/.*"
    __redirect_keywords__ = ["share"]

    async def _do_parse(self, raw_url: str) -> VideoParseResult | ImageParseResult | MultimediaParseResult:
        shortcode = self.get_short_code(raw_url)
        if not shortcode:
            raise ValueError("Instagram帖子链接无效")

        post = await self._parse(raw_url, shortcode)

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

    async def _parse(self, url: str, shortcode: str, cookie: SecretCookie | None = None) -> InstagramPost:
        try:
            api = InstagramAPI(proxy=self.proxy, cookie=cookie.get_value() if cookie else None, timeout=30)
            return await api.get_post(shortcode)
        except InstagramAPIError as e:
            match str(e):
                case "Fetching Post metadata failed.":
                    if self.cookie and cookie is None:
                        return await self._parse(url, shortcode, self.cookie)
                    else:
                        raise ParseError("受限视频无法解析: 你必须年满 18 周岁才能观看这个视频") from e
                case _:
                    raise ParseError("无法获取帖子内容(可能为私人内容)") from e
        except Exception as e:
            if cookie:
                text = f"Instagram 账号可能已被封禁\n\n使用的Cookie: {cookie}"
            else:
                text = str(e)
            raise ParseError(f"无法获取帖子内容(可能为私人内容): {text}") from e

    @staticmethod
    def get_short_code(url: str) -> str | None:
        url = url.removesuffix("/")
        shortcode = re.search(r"/(p|reel|reels|share|.*/p|.*/reel)/(.*)", url)
        return shortcode.group(2).split("/")[0] if shortcode else None


__all__ = ["InstagramParser"]
