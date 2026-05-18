from dataclasses import dataclass
from typing import Any, cast

import httpx
from bs4 import BeautifulSoup, Tag
from markdown import markdown
from markdownify import MarkdownConverter

from ..config import GlobalConfig
from ..types import ParseError


class WXConverter(MarkdownConverter):
    def convert_img(self, el, text, parent_tags):
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("data-src", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        options = cast(dict[str, Any], getattr(self, "options"))
        if "_inline" in parent_tags and el.parent.name not in options["keep_inline_images_in"]:
            return alt

        return f"![{alt}]({src}{title_part})"


@dataclass
class WX:
    title: str
    imgs: list[str]
    markdown_content: str
    text_content: str

    @staticmethod
    async def parse(url: str, proxy: str | None = None):
        async with httpx.AsyncClient(proxy=proxy) as client:
            response = await client.get(url, headers={"User-Agent": GlobalConfig.ua})
            html = response.text
            return WX._parse_html(html)

    @classmethod
    def _parse_html(cls, html: str) -> "WX":
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("h1", {"class": "rich_media_title"})
        title = title_tag.text.strip() if isinstance(title_tag, Tag) else ""
        wxc = WXConverter(heading_style="ATX")
        if isinstance(rich_media_content := soup.find("div", {"class": "rich_media_content"}), Tag):
            imgs = [str(i.get("data-src") or "") for i in rich_media_content.find_all("img", {"class": "rich_pages"})]

            markdown_content = wxc.convert(str(rich_media_content))
            text_content = "".join(BeautifulSoup(markdown(markdown_content), "lxml").find_all(string=True))
            return cls(title, imgs, markdown_content, text_content)
        elif isinstance(share_content_page := soup.find("div", {"class": "share_content_page"}), Tag):
            imgs = [str(i.get("data-src") or "") for i in share_content_page.find_all("div", {"class": "swiper_item"})]

            description = soup.find("meta", {"name": "description"})
            if not isinstance(description, Tag):
                raise ParseError("获取内容失败")
            markdown_content = wxc.convert(str(description.get("content") or ""))
            text_content = "".join(BeautifulSoup(markdown(markdown_content), "lxml").find_all(string=True))
            return cls(title, imgs, markdown_content, text_content)
        else:
            raise ParseError("获取内容失败")
