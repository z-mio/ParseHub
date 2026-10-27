from ...provider_api.zuiyou import MediaType, ZuiYou
from ...types import ImageRef, MultimediaParseResult, Platform, VideoRef
from ..base.base import BaseParser


class ZuiYouParser(BaseParser):
    __platform__ = Platform.ZUIYOU
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(share.xiaochuankeji.cn/hybrid/share/post\?pid=\d+|s.izuiyou.com/s/\w+)"
    __redirect_keywords__ = ["s.izuiyou.com/s/"]
    __reserved_parameters__ = ["pid"]

    async def _do_parse(self, raw_url: str) -> MultimediaParseResult:
        zy = await ZuiYou(self.proxy).parse(raw_url)
        return MultimediaParseResult(
            content=zy.content,
            media=[
                VideoRef(url=i.url, thumb_url=i.thumb_url)
                if i.type == MediaType.VIDEO
                else ImageRef(url=i.url, thumb_url=i.thumb_url)
                for i in zy.media
            ],
        )


__all__ = ["ZuiYouParser"]
