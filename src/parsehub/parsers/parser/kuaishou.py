from ...provider_api.kuaishou import KuaiShouAPI
from ...types import (
    ParseError,
    Video,
    VideoParseResult,
)
from ...types.platform import Platform
from ..base.base import BaseParser


class KuaiShouParser(BaseParser):
    __platform__ = Platform.KUAISHOU
    __supported_type__ = ["视频"]
    __match__ = r"^(http(s)?://)?(www|v)\.kuaishou.com/.+"
    __redirect_keywords__ = ["v.kuaishou", "/f/"]

    async def parse(self, url: str) -> VideoParseResult:
        ks = KuaiShouAPI(self.cfg.cookie)
        try:
            result = await ks.get_video_info(url)
        except Exception as e:
            raise ParseError(f"快手解析失败: {e}") from e
        else:
            return VideoParseResult(
                title=result.title,
                video=Video(
                    path=result.video_url,
                    thumb_url=result.thumb_url,
                    duration=result.duration,
                    height=result.height,
                    width=result.width,
                ),
                raw_url=url,
            )


__all__ = ["KuaiShouParser"]
