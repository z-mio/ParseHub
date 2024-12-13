from dataclasses import dataclass

from markdown import markdown

from ..base.base import Parser
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
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            html = response.text
            wx = parse_html(html)
            return WXImageParseResult(
                title=wx.title,
                photo=wx.imgs,
                desc=wx.text_content,
                raw_url=url,
            )


class WXImageParseResult(ImageParseResult):
    def __init__(
        self, title: str, photo: list[str], desc: str, raw_url: str, wx: "WX" = None
    ):
        super().__init__(title, photo, desc, raw_url)
        self.wx = wx


class WXConverter(MarkdownConverter):
    def convert_img(self, el, text, convert_as_inline):
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("data-src", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "%s"' % title.replace('"', r"\"") if title else ""
        if (
            convert_as_inline
            and el.parent.name not in self.options["keep_inline_images_in"]
        ):
            return alt

        return "![%s](%s%s)" % (alt, src, title_part)


def md(html, **options):
    return WXConverter(**options).convert(html)


@dataclass
class WX:
    title: str
    imgs: list[str]
    markdown_content: str
    text_content: str


def parse_html(html: str) -> WX:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", {"class": "rich_media_content"})

    if not content:
        raise ParseError("获取内容失败")

    title = (t := soup.find("h1", {"class": "rich_media_title"})) and t.text.strip()
    imgs = [i["data-src"] for i in content.find_all("img", {"class": "rich_pages"})]

    markdown_content = md(str(content), heading_style="ATX")
    text_content = "".join(
        BeautifulSoup(markdown(markdown_content), "html.parser").find_all(string=True)
    )
    return WX(title, imgs, markdown_content, text_content)
