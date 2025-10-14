from ...provider_api.weixin import WX
from ...types import ImageParseResult
from ..base.base import BaseParser


class WXParser(BaseParser):
    __platform_id__ = "weixin"
    __platform__ = "微信公众号"
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)mp.weixin.qq.com/s/.*"

    async def parse(self, url: str) -> "WXImageParseResult":
        url = await self.get_raw_url(url)
        wx = await WX.parse(url, self.cfg.proxy)
        return WXImageParseResult(
            title=wx.title,
            photo=wx.imgs,
            desc=wx.text_content,
            raw_url=url,
            wx=wx,
        )


class WXImageParseResult(ImageParseResult):
    def __init__(self, title: str, photo: list[str], desc: str, raw_url: str, wx: "WX"):
        super().__init__(title, photo, desc, raw_url)
        self.wx = wx


__all__ = ["WXParser", "WXImageParseResult"]
