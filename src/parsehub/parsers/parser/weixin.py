from ...provider_api.weixin import WX
from ...types import RichTextParseResult
from ...types.platform import Platform
from ..base.base import BaseParser


class WXParser(BaseParser):
    __platform__ = Platform.WEIXIN
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)mp.weixin.qq.com/s/.*"

    async def parse(self, url: str) -> "WXRichTextParseResult":
        url = await self.get_raw_url(url)
        wx = await WX.parse(url, self.cfg.proxy)
        return WXRichTextParseResult(
            title=wx.title,
            media=wx.imgs,
            markdown_content=wx.markdown_content,
            raw_url=url,
        )


class WXRichTextParseResult(RichTextParseResult): ...


__all__ = ["WXParser", "WXRichTextParseResult"]
