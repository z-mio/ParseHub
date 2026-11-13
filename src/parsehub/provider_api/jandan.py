from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from ..errors import ContentUnavailableError
from ..utils.helpers import UA

_POST_NO_RE = re.compile(r"No\.\s*\d+")


@dataclass
class JandanPost:
    """煎蛋帖子的解析结果

    Attributes:
        title: 标题
        markdown_content: markdown 正文
        images: 正文内的图片地址
    """

    title: str
    markdown_content: str
    images: list[str] = field(default_factory=list)


class Jandan:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, url: str) -> JandanPost:
        async with httpx.AsyncClient(proxy=self.proxy, timeout=30, headers={"User-Agent": UA}) as client:
            response = await client.get(url)
        if response.status_code == 404:
            raise ContentUnavailableError("煎蛋内容不存在或已删除")
        if not 200 <= response.status_code < 300:
            raise JandanError(f"HTTP {response.status_code}")
        return self._parse_html(response.text, str(response.url))

    @staticmethod
    def _parse_html(html: str, page_url: str) -> JandanPost:
        soup = BeautifulSoup(html, "lxml")
        content = soup.select_one(".post-content")
        if content is None:
            raise JandanError("未找到煎蛋正文")

        heading = soup.find("h1")
        for a in content.find_all("a", href=True):
            a["href"] = urljoin(page_url, str(a["href"]))
        converter = _JandanMarkdownConverter(page_url)
        markdown_content = converter.convert(str(content)).strip()
        return JandanPost(
            title=_compose_title(
                heading.get_text(strip=True) if heading else "",
                _first_line(content.get_text("\n", strip=True)),
            ),
            markdown_content=markdown_content,
            images=converter.images,
        )


def _first_line(text: str, limit: int = 80) -> str:
    line = next((line for line in text.splitlines() if line.strip()), "")
    return " ".join(line.split())[:limit]


def _compose_title(heading: str, first_line: str) -> str:
    """话题帖的标题只是 "No.6209188", 这时用正文首行代替."""
    heading = " ".join(heading.split())
    if heading and not _POST_NO_RE.fullmatch(heading):
        return heading
    return first_line or heading


class _JandanMarkdownConverter(MarkdownConverter):
    """把正文 HTML 转为 markdown 并收集图片地址."""

    def __init__(self, page_url: str) -> None:
        super().__init__(heading_style="ATX")
        self.page_url = page_url
        self.images: list[str] = []

    def convert_img(self, el: Any, text: Any, parent_tags: Any) -> str:
        alt = el.attrs.get("alt") or ""
        source = el.attrs.get("src") or ""
        url = urljoin(self.page_url, source) if source else ""
        if not url:
            return alt
        if url not in self.images:
            self.images.append(url)
        return f"![{alt}]({url})"


class JandanError(Exception):
    pass


__all__ = ["Jandan", "JandanError", "JandanPost"]
