from ...provider_api.weixin import WX, WXItemShowType
from ...types import AnyParseResult, ImageParseResult, ImageRef, ParseError, Platform, RichTextParseResult
from ..base.base import BaseParser


class WXParser(BaseParser):
    __platform__ = Platform.WEIXIN
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)mp.weixin.qq.com/s/.*"

    @staticmethod
    def _refs(urls: list[str]) -> list[ImageRef]:
        """图片地址带 wx_fmt 参数标明实际格式, 缺失时才用默认的 jpg."""
        refs = []
        for url in urls:
            fmt = url.partition("wx_fmt=")[2].partition("&")[0]
            refs.append(ImageRef(url=url, ext=fmt or "jpg"))
        return refs

    async def _do_parse(self, raw_url: str) -> AnyParseResult:
        wx = await WX.parse(raw_url, self.proxy)

        match wx.item_show_type:
            case WXItemShowType.ARTICLE:
                return RichTextParseResult(
                    title=wx.title,
                    media=self._refs(wx.imgs),
                    markdown_content=wx.markdown_content,
                )
            case WXItemShowType.IMAGE | WXItemShowType.TEXT:
                return ImageParseResult(
                    title=wx.title,
                    photo=self._refs(wx.photos),
                    content=wx.text_content,
                )
            case _:
                raise ParseError(f"不支持的内容类型: {wx.item_show_type!r}")


__all__ = ["WXParser"]
