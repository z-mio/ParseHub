from ...provider_api.weixin import WX
from ...types import ImageRef, Platform, RichTextParseResult
from ..base.base import BaseParser


class WXParser(BaseParser):
    __platform__ = Platform.WEIXIN
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)mp.weixin.qq.com/s/.*"

    async def _do_parse(self, raw_url: str) -> "RichTextParseResult":
        wx = await WX.parse(raw_url, self.cfg.proxy)
        return RichTextParseResult(
            title=wx.title,
            media=[ImageRef(url=i) for i in wx.imgs],
            markdown_content=wx.markdown_content,
            raw_url=raw_url,
        )


__all__ = ["WXParser"]
