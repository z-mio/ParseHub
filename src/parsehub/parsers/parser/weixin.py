from ...provider_api.weixin import WX
from ...types import Platform, RichTextParseResult
from ..base.base import BaseParser


class WXParser(BaseParser):
    __platform__ = Platform.WEIXIN
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)mp.weixin.qq.com/s/.*"

    async def _do_parse(self, raw_url: str) -> "WXRichTextParseResult":
        wx = await WX.parse(raw_url, self.cfg.proxy)
        return WXRichTextParseResult(
            title=wx.title,
            media=wx.imgs,
            markdown_content=wx.markdown_content,
            raw_url=raw_url,
        )


class WXRichTextParseResult(RichTextParseResult): ...


__all__ = ["WXParser", "WXRichTextParseResult"]
