from typing import Union
from ...deps.xhs.source import XHS
from ..base import Parser
from ...types import (
    VideoParseResult,
    ImageParseResult,
    ParseError,
    MultimediaParseResult,
    Video,
    Image,
)


class Log:
    """用来隐藏日志"""

    @staticmethod
    def write(*args, **kwargs):
        # print(args, kwargs)
        ...


class XhsParser(Parser):
    __platform_id__ = "xhs"
    __platform__ = "小红书"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(xiaohongshu|xhslink).com/.+"
    __redirect_keywords__ = ["xhslink", "item"]
    __reserved_parameters__ = ["xsec_token"]

    async def parse(
        self, url: str
    ) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        url = await self.get_raw_url(url)
        async with XHS(user_agent="", cookie="") as xhs:
            x_result = await xhs.extract(url, False, log=Log)
        if not x_result or not (result := x_result[0]):
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
                photo=[
                    Image(i if i.endswith("?") else i + "?", ext="png")
                    for i in result["下载地址"]
                ],
                **k,
            )
        else:
            raise ParseError("不支持的类型")


__all__ = ["XhsParser"]
