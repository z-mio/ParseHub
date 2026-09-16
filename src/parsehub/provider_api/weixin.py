import re
from dataclasses import dataclass
from enum import IntEnum
from html import unescape
from typing import Any, cast

import httpx
import json5
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from ..errors import ParseError
from ..utils.helpers import UA


class WXItemShowType(IntEnum):
    """页面数据里的 ``item_show_type``, 决定正文与媒体的取值位置."""

    ARTICLE = 0
    """公众号文章"""
    IMAGE = 8
    """图文"""
    TEXT = 10
    """纯文本"""


_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_IMG_SRC_RE = re.compile(r"<img[^>]*?\bdata-src\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
#: 页面数据用 '0' * 1 这类写法做隐式类型转换, 不是合法的 JSON5 值
_IMPLICIT_INT_RE = re.compile(r"('[^'\n]*'|\"[^\"\n]*\")\s*\*\s*1(?![.\d])")
#: 对象以 "};" 结束后还跟着 try/catch 与 IIFE 收尾
_OBJECT_END_RE = re.compile(r"}\s*;.*$", re.DOTALL)

_PAYLOAD_NAME = "cgiDataNew"


def _load_payload(html: str) -> dict[str, Any]:
    """解析 ``window.cgiDataNew`` 为字典.

    数据在 script 标签里, 是 JS 对象字面量 (键无引号、单引号字符串、尾随逗号),
    用 json5 解析, 只需去掉两处 JS 语法.
    """
    scripts = [s.text for s in BeautifulSoup(html, "lxml").find_all("script") if _PAYLOAD_NAME in s.text]
    if not scripts:
        raise ParseError(f"未找到 {_PAYLOAD_NAME} 数据")

    text = scripts[0].split(_PAYLOAD_NAME, 1)[1]
    text = _IMPLICIT_INT_RE.sub(r"\1", text)
    text = text[text.index("{") :]
    return cast(dict[str, Any], json5.loads(_OBJECT_END_RE.sub("}", text, count=1)))


def _to_text(source: Any) -> str:
    """正文片段转纯文本, 兼容本身就是纯文本的情况."""
    if not isinstance(source, str) or not source:
        return ""
    return unescape(_TAG_RE.sub("", _BREAK_RE.sub("\n", unescape(source)))).strip()


def _collect_photos(data: dict[str, Any]) -> list[str]:
    """图片消息的图片地址, 取原始图 ``watermark_info.cdn_url``, 缺失时退回 ``cdn_url``."""
    entries = data.get("picture_page_info_list") or []
    return [
        url
        for e in entries
        if isinstance(e, dict)
        for url in [(e.get("watermark_info") or {}).get("cdn_url") or e.get("cdn_url")]
        if url
    ]


class WXConverter(MarkdownConverter):
    """把正文 HTML 转为 markdown, 图片地址取自 ``data-src``."""

    def convert_img(self, el: Any, text: Any, parent_tags: Any) -> str:
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("data-src", None) or el.attrs.get("src", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        options = cast(dict[str, Any], getattr(self, "options"))  # noqa: B009
        if "_inline" in parent_tags and el.parent.name not in options["keep_inline_images_in"]:
            return alt

        return f"![{alt}]({src}{title_part})"


@dataclass
class WX:
    """微信文章的解析结果.

    Attributes:
        item_show_type: 内容形态
        title: 标题
        markdown_content: markdown 正文, 仅图文形态有值
        imgs: 正文内的图片地址
        text_content: 纯文本正文
        photos: 图片消息的图片地址, 仅图片形态有值
    """

    item_show_type: WXItemShowType
    title: str
    markdown_content: str
    imgs: list[str]
    text_content: str
    photos: list[str]

    @staticmethod
    async def parse(url: str, proxy: str | None = None) -> "WX":
        async with httpx.AsyncClient(proxy=proxy) as client:
            response = await client.get(url, headers={"User-Agent": UA})
        return WX._parse_data(response.text)

    @classmethod
    def _parse_data(cls, html: str) -> "WX":
        data = _load_payload(html)
        try:
            item_show_type = WXItemShowType(int(data["item_show_type"]))
        except (KeyError, TypeError, ValueError) as e:
            raise ParseError(f"不支持的内容类型: {data.get('item_show_type')!r}") from e

        match item_show_type:
            case WXItemShowType.ARTICLE:
                source = data.get("content_noencode") or ""
                return cls(
                    item_show_type=item_show_type,
                    title=data.get("title") or "",
                    markdown_content=WXConverter(heading_style="ATX").convert(source),
                    imgs=_IMG_SRC_RE.findall(source),
                    text_content=_to_text(source),
                    photos=[],
                )
            case WXItemShowType.TEXT:
                return cls(
                    item_show_type=item_show_type,
                    title="",
                    markdown_content="",
                    imgs=[],
                    text_content=_to_text((data.get("text_page_info") or {}).get("content_noencode")),
                    photos=[],
                )
            case WXItemShowType.IMAGE:
                return cls(
                    item_show_type=item_show_type,
                    title=data.get("title") or "",
                    markdown_content="",
                    imgs=[],
                    text_content=_to_text(data.get("content_noencode")),
                    photos=_collect_photos(data),
                )


__all__ = ["WX", "WXConverter", "WXItemShowType"]
