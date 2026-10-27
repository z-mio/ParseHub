import re
from typing import Union

from ...provider_api.xhs import MOBILE_HEADERS, PC_HEADERS, XHSAPI, XHSMedia, XHSMediaType, XHSPost, XHSPostType
from ...types import (
    ContentUnavailableError,
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    MultimediaParseResult,
    ParseError,
    Platform,
    VideoParseResult,
    VideoRef,
)
from ..base.base import BaseParser, FallbackStage


class XHSParser(BaseParser):
    __platform__ = Platform.XHS
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).(com|cn)/.+"
    __redirect_keywords__ = ["xhslink"]
    __after_clean_parameters__ = ["xsec_token", "xsec_source"]

    async def get_raw_url(self, url: str, *, clean_all: bool = False, headers: dict | None = None) -> str:
        url = await super().get_raw_url(url, clean_all=clean_all, headers=MOBILE_HEADERS)
        if "/login" in url:
            raise ParseError("该帖子需要登录后查看")
        elif "/404/sec" in url:
            raise ParseError("被小红书风控拦截")
        elif "/404" in url:
            raise ContentUnavailableError("帖子不存在")
        return url

    async def _do_parse(self, raw_url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        xhs = XHSAPI(proxy=self.proxy)
        stages: list[FallbackStage[XHSPost]] = []
        if cookie := self.cookie.get_value():

            async def parse_cookie() -> XHSPost:
                return await xhs.extract(raw_url, PC_HEADERS, cookie)

            stages.append(FallbackStage("cookie", parse_cookie, cookie=True))

        async def parse_session() -> XHSPost:
            return await xhs.extract(raw_url, PC_HEADERS, await xhs.new_session())

        async def parse_mobile() -> XHSPost:
            return await xhs.extract(raw_url, MOBILE_HEADERS)

        stages.extend(
            [
                FallbackStage("游客 session", parse_session),
                FallbackStage("移动端", parse_mobile),
            ]
        )
        result = await self._fallback(*stages, stop=lambda e: False)

        desc = self.hashtag_handler(result.desc)
        match result.type:
            case XHSPostType.VIDEO:
                if not result.media:
                    raise ParseError("未获取到视频")
                v: XHSMedia = result.media[0]
                return VideoParseResult(
                    video=VideoRef(
                        url=v.url, thumb_url=v.thumb_url, duration=v.duration, height=v.height, width=v.width
                    ),
                    title=result.title,
                    content=desc,
                )
            case XHSPostType.IMAGE:
                media_list = result.media or []
                photos: list[ImageRef | LivePhotoRef] = []
                for i in media_list:
                    if i.type == XHSMediaType.LIVE_PHOTO:
                        photos.append(
                            LivePhotoRef(url=i.thumb_url or "", video_url=i.url, width=i.width, height=i.height)
                        )
                    else:
                        photos.append(
                            ImageRef(url=i.url, ext="jpg", thumb_url=i.thumb_url, width=i.width, height=i.height)
                        )

                return ImageParseResult(
                    photo=photos,
                    title=result.title,
                    content=desc,
                )
            case _:
                raise ParseError("不支持的类型")

    @staticmethod
    def hashtag_handler(desc: str | None) -> str:
        if not desc:
            return ""
        hashtags = re.findall(r" ?#[^#\[\]]+\[话题]# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f"{hashtag.strip().replace('[话题]#', '')} ")
        return desc.strip()


__all__ = ["XHSParser"]
