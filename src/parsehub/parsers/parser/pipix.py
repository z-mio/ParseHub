from typing import Union

from ...provider_api.pipix import Pipix
from ...types import ImageParseResult, ParseError, Video, VideoParseResult
from ..base.base import BaseParser


class PipixParser(BaseParser):
    __platform_id__ = "pipix"
    __platform__ = "皮皮虾"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?h5.pipix.com/(s|ppx/item)/.+"
    __redirect_keywords__ = ["/s/"]

    async def parse(self, url: str) -> Union["ImageParseResult", "VideoParseResult"]:
        try:
            ppx = await Pipix(self.cfg.proxy).parse(url)
        except Exception as e:
            raise ParseError("皮皮虾解析失败") from e

        if ppx.video_url:
            return VideoParseResult(
                title=ppx.content,
                video=Video(
                    ppx.video_url,
                    thumb_url=ppx.video_thumb,
                    duration=ppx.video_duration,
                    height=ppx.video_height,
                    width=ppx.video_width,
                ),
                raw_url=url,
            )
        else:
            return ImageParseResult(title=ppx.content, photo=ppx.img_url, raw_url=url)


__all__ = ["PipixParser"]
