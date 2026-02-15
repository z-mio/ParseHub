from ...provider_api.zuiyou import MediaType, ZuiYou
from ...types import ImageRef, MultimediaParseResult, VideoRef
from ...types.platform import Platform
from ..base.base import BaseParser


class ZuiYouParser(BaseParser):
    __platform__ = Platform.ZUIYOU
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)share.xiaochuankeji.cn/hybrid/share/post\?pid=\d+"
    __reserved_parameters__ = ["pid"]

    async def parse(self, url: str) -> MultimediaParseResult:
        zy = await ZuiYou(self.cfg.proxy).parse(url)
        return MultimediaParseResult(
            content=zy.content,
            media=[
                VideoRef(url=i.url, thumb_url=i.thumb_url)
                if i.type == MediaType.VIDEO
                else ImageRef(url=i.url, thumb_url=i.thumb_url)
                for i in zy.media
            ],
            raw_url=url,
        )


__all__ = ["ZuiYouParser"]
