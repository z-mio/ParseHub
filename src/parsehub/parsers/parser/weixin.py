from dataclasses import dataclass

from markdown import markdown

from ..base.base import Parser
from ...config import GlobalConfig
from ...types import ImageParseResult, ParseError

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
import httpx


class WXParser(Parser):
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


class WXConverter(MarkdownConverter):
    def convert_img(self, el, text, parent_tags):
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("data-src", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "%s"' % title.replace('"', r"\"") if title else ""
        if (
            "_inline" in parent_tags
            and el.parent.name not in self.options["keep_inline_images_in"]
        ):
            return alt

        return "![%s](%s%s)" % (alt, src, title_part)

    @classmethod
    def md(cls, html, **options):
        return cls(**options).convert(html)


@dataclass
class WX:
    title: str
    imgs: list[str]
    markdown_content: str
    text_content: str

    @staticmethod
    async def parse(url: str, proxy: str):
        async with httpx.AsyncClient(proxies=proxy) as client:
            response = await client.get(url, headers={"User-Agent": GlobalConfig.ua})
            html = response.text
            return WX._parse_html(html)

    @classmethod
    def _parse_html(cls, html: str) -> "WX":
        soup = BeautifulSoup(html, "html.parser")
        title = (t := soup.find("h1", {"class": "rich_media_title"})) and t.text.strip()

        if rich_media_content := soup.find("div", {"class": "rich_media_content"}):
            imgs = [i["data-src"] for i in rich_media_content.find_all("img", {"class": "rich_pages"})]

            markdown_content = WXConverter.md(str(rich_media_content), heading_style="ATX")
            text_content = "".join(
                BeautifulSoup(markdown(markdown_content), "html.parser").find_all(
                    string=True
                )
            )
            return cls(title, imgs, markdown_content, text_content)
        elif share_content_page := soup.find("div", {"class": "share_content_page"}):
            imgs = [i["data-src"] for i in share_content_page.find_all("div", {"class": "swiper_item"})]

            markdown_content = WXConverter.md(soup.find('meta',{'name':"description"})['content'], heading_style="ATX")
            text_content = "".join(
                BeautifulSoup(markdown(markdown_content), "html.parser").find_all(
                    string=True
                )
            )
            return cls(title, imgs, markdown_content, text_content)
        else:
            raise ParseError("获取内容失败")

