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
from ...utils.utils import clear_params
from ..base import BaseParser


class XHSParser(BaseParser):
    __platform__ = Platform.XHS
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).com/.+"
    __redirect_keywords__ = ["xhslink", "item"]
    __reserved_parameters__ = ["xsec_token"]

    async def _do_parse(self, raw_url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        raw_url = clear_params(raw_url, "xsec_token")
        xhs = XHSAPI(proxy=self.cfg.proxy)
        result = await xhs.extract(raw_url)

        desc = self.hashtag_handler(result.desc)
        k = {"title": result.title, "content": desc, "raw_url": raw_url}
        match result.type:
            case XHSPostType.VIDEO:
                v: XHSMedia = result.media[0]
                return VideoParseResult(
                    video=VideoRef(
                        url=v.url, thumb_url=v.thumb_url, duration=v.duration, height=v.height, width=v.width
                    ),
                    **k,
                )
            case XHSPostType.IMAGE:
                photos: list[ImageRef | LivePhotoRef] = []
                for i in result.media:
                    if i.type == XHSMediaType.LIVE_PHOTO:
                        photos.append(LivePhotoRef(url=i.thumb_url, video_url=i.url, width=i.width, height=i.height))
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
                    **k,
                )
            case _:
                raise ParseError("不支持的类型")

    async def get_ext_by_url(self, url: str):
        async with httpx.AsyncClient(proxy=self.cfg.proxy) as client:
            try:
                response = await client.head(url, follow_redirects=True)
            except Exception:
                return ""

            if content_type := response.headers.get("content-type"):
                media_type = content_type.split(";")[0].strip()
                if "/" in media_type:
                    extension = media_type.split("/")[-1]
                    return extension

            return ""

    @staticmethod
    def hashtag_handler(desc: str | None):
        if not desc:
            return None
        hashtags = re.findall(r" ?#[^#\[\]]+\[话题]# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f"{hashtag.strip().replace('[话题]#', '')} ")
        return desc.strip()


__all__ = ["XHSParser"]
