from typing import Union

import httpx

from ...deps.xhs.source import XHS
from ...types import (
    Image,
    ImageParseResult,
    MultimediaParseResult,
    ParseError,
    Video,
    VideoParseResult,
)
from ..base import BaseParser


class Log:
    """用来隐藏日志"""

    @staticmethod
    def write(*args, **kwargs):
        # print(args, kwargs)
        ...


class XhsParser(BaseParser):
    __platform_id__ = "xhs"
    __platform__ = "小红书"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).com/.+"
    __redirect_keywords__ = ["xhslink", "item"]
    __reserved_parameters__ = ["xsec_token"]

    async def parse(self, url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        url = await self.get_raw_url(url)
        async with XHS(user_agent="", cookie="") as xhs:
            x_result = await xhs.extract(url, False, log=Log)
        if not x_result or not (result := x_result[0]):
            raise ParseError("小红书解析失败")
        k = {"title": result["作品标题"], "desc": result["作品描述"], "raw_url": url}

        if all(result["动图地址"]):
            # livephoto
            return MultimediaParseResult(media=[Video(i) for i in result["动图地址"]], **k)
        elif result["作品类型"] == "视频":
            return VideoParseResult(video=result["下载地址"][0], **k)
        elif result["作品类型"] == "图文":
            photos = []
            for i in result["下载地址"]:
                img_url = i if i.endswith("?") else i + "?"
                ext = (await self.get_ext_by_url(img_url)) or "png"
                photos.append(Image(img_url, ext))
            return ImageParseResult(
                photo=photos,
                **k,
            )
        else:
            raise ParseError("不支持的类型")

    @staticmethod
    async def get_ext_by_url(url: str):
        async with httpx.AsyncClient() as client:
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


__all__ = ["XhsParser"]
