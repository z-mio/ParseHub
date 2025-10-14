from typing import Union

from ...provider_api.tieba import TieBa
from ...types import ImageParseResult, ParseError, VideoParseResult
from ..base.base import BaseParser


class TieBaParser(BaseParser):
    __platform_id__ = "tieba"
    __platform__ = "贴吧"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+tieba.baidu.com/p/\d+"

    async def parse(self, url: str) -> Union["ImageParseResult", "VideoParseResult"]:
        try:
            tb = await TieBa(self.cfg.proxy).parse(url)
        except Exception as e:
            raise ParseError("贴吧解析失败") from e

        if tb.video_url:
            return VideoParseResult(title=tb.title, video=tb.video_url, raw_url=url, desc=tb.content)
        else:
            return ImageParseResult(title=tb.title, photo=tb.img_url, raw_url=url, desc=tb.content)


__all__ = ["TieBaParser"]
