from typing import Union
from ...deps.xhs.source import XHS
from ..base.base import Parser
from ...types import (
    VideoParseResult,
    ImageParseResult,
    ParseError,
    MultimediaParseResult,
    Video,
    Image,
)


class log:
    """用来隐藏日志"""

    @staticmethod
    def write(*args, **kwargs): ...


class XhsParser(Parser):
    __platform__ = "小红书"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).com/.+"
    __redirect_keywords__ = ["xhslink"]
    __reserved_parameters__ = ["xsec_token"]

    async def parse(
        self, url: str
    ) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        url = await self.get_raw_url(url)

        async with XHS(user_agent="", cookie="") as xhs:
            result = await xhs.extract(url, False, log=log)
        if not (result := result[0]):
            raise ParseError("小红书解析失败")

        k = {"title": result["作品标题"], "desc": result["作品描述"], "raw_url": url}

        if all(result["动图地址"]):
            # livephoto
            return MultimediaParseResult(
                media=[Video(i) for i in result["动图地址"]], **k
            )
        elif result["作品类型"] == "视频":
            return VideoParseResult(video=result["下载地址"][0], **k)
        elif result["作品类型"] == "图文":
            return ImageParseResult(
                photo=[Image(i, ext="png") for i in result["下载地址"]], **k
            )
