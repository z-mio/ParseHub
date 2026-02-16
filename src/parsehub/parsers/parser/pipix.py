from typing import Union

from ...provider_api.pipix import Pipix
from ...types import ImageParseResult, ParseError, VideoParseResult, VideoRef
from ...types.platform import Platform
from ..base.base import BaseParser


class PipixParser(BaseParser):
    __platform__ = Platform.PIPIX
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?h5.pipix.com/(s|ppx/item)/.+"
    __redirect_keywords__ = ["/s/"]

    async def _do_parse(self, raw_url: str) -> Union["ImageParseResult", "VideoParseResult"]:
        try:
            ppx = await Pipix(self.cfg.proxy).parse(raw_url)
        except Exception as e:
            raise ParseError("皮皮虾解析失败") from e

        if ppx.video_url:
            return VideoParseResult(
                title=ppx.content,
                video=VideoRef(
                    url=ppx.video_url,
                    thumb_url=ppx.video_thumb,
                    duration=ppx.video_duration,
                    height=ppx.video_height,
                    width=ppx.video_width,
                ),
                raw_url=raw_url,
            )
        else:
            return ImageParseResult(title=ppx.content, photo=ppx.img_url, raw_url=raw_url)


__all__ = ["PipixParser"]
