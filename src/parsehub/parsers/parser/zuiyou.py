from ...provider_api.zuiyou import MediaType, ZuiYou
from ...types import Image, MultimediaParseResult, Video
from ..base.base import BaseParser


class ZuiYouParser(BaseParser):
    __platform_id__ = "zuiyou"
    __platform__ = "最右"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)share.xiaochuankeji.cn/hybrid/share/post\?pid=\d+"
    __reserved_parameters__ = ["pid"]

    async def parse(self, url: str) -> MultimediaParseResult:
        url = await self.get_raw_url(url)
        zy = await ZuiYou(self.cfg.proxy).parse(url)
        return MultimediaParseResult(
            desc=zy.content,
            media=[
                Video(path=i.url, thumb_url=i.thumb_url)
                if i.type == MediaType.VIDEO
                else Image(path=i.url, thumb_url=i.thumb_url)
                for i in zy.media
            ],
            raw_url=url,
        )


__all__ = ["ZuiYouParser"]
