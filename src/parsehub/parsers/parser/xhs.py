import re
from typing import Union

import httpx

from ...provider_api.xhs import XHSAPI, XHSMedia, XHSMediaType, XHSPostType
from ...types import (
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    MultimediaParseResult,
    ParseError,
    Platform,
    VideoParseResult,
    VideoRef,
)
from ..base import BaseParser


class XHSParser(BaseParser):
    __platform__ = Platform.XHS
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).(com|cn)/.+"
    __redirect_keywords__ = ["xhslink"]
    __after_clean_parameters__ = ["xsec_token"]

    async def _do_parse(self, raw_url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        xhs = XHSAPI(proxy=self.proxy, cookie=self.cookie.get_value())
        result = await xhs.extract(raw_url)

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
                        # 小红书图片格式: "png" | "webp" | "jpeg" | "heic" | "avif"
                        ext = await self.get_ext_by_url(i.url)
                        if ext not in ["png", "webp", "jpeg", "heic", "avif"]:
                            ext = "jpeg"
                        photos.append(
                            ImageRef(url=i.url, ext=ext, thumb_url=i.thumb_url, width=i.width, height=i.height)
                        )

                return ImageParseResult(
                    photo=photos,
                    title=result.title,
                    content=desc,
                )
            case _:
                raise ParseError("不支持的类型")

    async def get_ext_by_url(self, url: str) -> str:
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            try:
                response = await client.head(url, follow_redirects=True)
            except Exception:
                return ""

            if content_type := response.headers.get("content-type"):
                media_type = content_type.split(";")[0].strip()
                if "/" in media_type:
                    extension = media_type.split("/")[-1]
                    return str(extension)

            return ""

    @staticmethod
    def hashtag_handler(desc: str | None) -> str:
        if not desc:
            return ""
        hashtags = re.findall(r" ?#[^#\[\]]+\[话题]# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f"{hashtag.strip().replace('[话题]#', '')} ")
        return desc.strip()


__all__ = ["XHSParser"]
