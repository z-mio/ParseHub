import re
from typing import Union
from urllib.parse import parse_qs, urlparse

import httpx

from ...provider_api.xhs import XHSAPI, MediaType, PostType
from ...provider_api.xhs import Media as XHSMedia
from ...types import (
    Image,
    ImageParseResult,
    MultimediaParseResult,
    ParseError,
    Video,
    VideoParseResult,
)
from ..base import BaseParser


class XhsParser(BaseParser):
    __platform_id__ = "xhs"
    __platform__ = "小红书"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).com/.+"
    __redirect_keywords__ = ["xhslink", "item"]
    __reserved_parameters__ = ["xsec_token"]

    @staticmethod
    async def clear_params(url: str) -> str:
        """
        清理 xsec_token 参数, 清理后只能用 app 访问该帖子
        :param url:
        :return:
        """
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        del query_params["xsec_token"]
        new_query = "&".join([f"{k}={v[0]}" for k, v in query_params.items()])
        return parsed_url._replace(query=new_query).geturl()

    async def parse(self, url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        url = await self.get_raw_url(url)
        raw_url = await self.clear_params(url)
        xhs = XHSAPI(proxy=self.cfg.proxy)
        result = await xhs.extract(url)

        desc = self.hashtag_handler(result.desc)
        k = {"title": result.title, "desc": desc, "raw_url": raw_url}
        match result.type:
            case PostType.VIDEO:
                v: XHSMedia = result.media[0]
                return VideoParseResult(
                    video=Video(path=v.url, thumb_url=v.thumb_url, duration=v.duration, height=v.height, width=v.width),
                    **k,
                )
            case PostType.IMAGE:
                photos = []
                for i in result.media:
                    if i.type == MediaType.LIVE_PHOTO:
                        photos.append(Video(i.url, thumb_url=i.thumb_url, width=i.width, height=i.height))
                    else:
                        # 小红书图片格式: "png" | "webp" | "jpeg" | "heic" | "avif"
                        ext = await self.get_ext_by_url(i.url)
                        if ext not in ["png", "webp", "jpeg", "heic", "avif"]:
                            ext = "jpeg"
                        photos.append(Image(i.url, ext, thumb_url=i.thumb_url, width=i.width, height=i.height))

                return MultimediaParseResult(
                    media=photos,
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
    def hashtag_handler(desc: str):
        hashtags = re.findall(r" ?#[^#\[\]]+\[话题]# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f"{hashtag.strip().replace('[话题]#', '')} ")
        return desc.strip()


__all__ = ["XhsParser"]
