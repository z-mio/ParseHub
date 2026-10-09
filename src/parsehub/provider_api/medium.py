from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from curl_cffi import requests

_ID_RE = re.compile(r"(?:^|-)([0-9a-f]{8,12})$")
_GRAPHQL_URL = "https://medium.com/_/graphql"
_GRAPHQL_QUERY = """
query P($id: ID!) {
  post(id: $id) {
    title
    isLocked
    content {
      bodyModel {
        paragraphs {
          type
          text
          href
          markups {
            type
            start
            end
            href
          }
          metadata {
            id
            originalWidth
            originalHeight
          }
          codeBlockMetadata {
            lang
          }
          iframe {
            mediaResource {
              href
              iframeSrc
              title
            }
          }
          mixtapeMetadata {
            href
          }
        }
      }
    }
  }
}
"""


@dataclass
class MediumImage:
    url: str
    width: int = 0
    height: int = 0


@dataclass
class MediumPost:
    title: str
    markdown_content: str
    images: list[MediumImage]


class Medium:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, url: str) -> MediumPost:
        path = urlparse(url).path.rstrip("/")
        path_segment = path.rsplit("/", 1)[-1]
        match = _ID_RE.search(path_segment)
        if not match:
            raise MediumError("不支持的 Medium 链接")
        post_id = match.group(1)

        async with requests.AsyncSession(impersonate="chrome", proxy=self.proxy, timeout=30) as session:
            response = await session.post(
                _GRAPHQL_URL,
                json=[
                    {
                        "operationName": "P",
                        "variables": {"id": post_id},
                        "query": _GRAPHQL_QUERY,
                    }
                ],
            )
            if not 200 <= response.status_code < 300:
                raise MediumError(f"HTTP {response.status_code}")

            result = response.json()[0]
            errors = result.get("errors")
            if errors:
                raise MediumError(errors[0]["message"])

            post = result["data"]["post"]
            if post is None:
                raise MediumError("内容不存在或已删除")

            paragraphs = post.get("content", {}).get("bodyModel", {}).get("paragraphs", [])
            markdown_content, images = _render_paragraphs(paragraphs, post.get("title") or "")
            return MediumPost(
                title=post.get("title") or "",
                markdown_content=markdown_content,
                images=images,
            )


def _render_paragraphs(paragraphs: list[dict[str, Any]], title: str) -> tuple[str, list[MediumImage]]:
    images: list[MediumImage] = []
    rendered_paragraphs: list[tuple[str, str]] = []
    ordered_count = 0

    for index, paragraph in enumerate(paragraphs):
        paragraph_type = paragraph.get("type") or ""
        text = paragraph.get("text") or ""
        if index == 0 and paragraph_type in {"H2", "H3", "H4"} and text.strip() == title.strip():
            continue

        content = _render_paragraph(paragraph, images)
        if content is None or not content.strip():
            continue

        if paragraph_type == "ULI":
            content = f"- {content}"
            ordered_count = 0
        elif paragraph_type == "OLI":
            ordered_count = ordered_count + 1 if rendered_paragraphs and rendered_paragraphs[-1][0] == "OLI" else 1
            content = f"{ordered_count}. {content}"
        else:
            ordered_count = 0

        rendered_paragraphs.append((paragraph_type, content))

    markdown_parts: list[str] = []
    previous_type = ""
    for paragraph_type, content in rendered_paragraphs:
        if markdown_parts:
            is_consecutive_list = paragraph_type in {"ULI", "OLI"} and previous_type in {"ULI", "OLI"}
            markdown_parts.append("\n" if is_consecutive_list else "\n\n")
        markdown_parts.append(content)
        previous_type = paragraph_type

    return "".join(markdown_parts).strip(), images


def _render_paragraph(paragraph: dict[str, Any], images: list[MediumImage]) -> str | None:
    paragraph_type = paragraph.get("type") or ""
    text = paragraph.get("text") or ""
    if paragraph_type == "IMG":
        metadata = paragraph.get("metadata") or {}
        image_id = metadata.get("id")
        if not image_id:
            return None
        image = MediumImage(
            url=f"https://miro.medium.com/v2/{image_id}",
            width=int(metadata.get("originalWidth") or 0),
            height=int(metadata.get("originalHeight") or 0),
        )
        images.append(image)
        markdown = f"![]({image.url})"
        caption = text.strip()
        if caption:
            markdown += f"\n*{caption}*"
        return markdown

    if paragraph_type == "PRE":
        language = (paragraph.get("codeBlockMetadata") or {}).get("lang") or ""
        return f"```{language}\n{text}\n```"

    if paragraph_type == "IFRAME":
        media_resource = (paragraph.get("iframe") or {}).get("mediaResource") or {}
        href = media_resource.get("href") or media_resource.get("iframeSrc")
        if not href:
            return None
        return f"[{media_resource.get('title') or href}]({href})"

    if paragraph_type == "MIXTAPE_EMBED":
        href = (paragraph.get("mixtapeMetadata") or {}).get("href")
        linked_text = _render_markup(text, paragraph.get("markups") or [])
        return f"[{linked_text}]({href})" if href else linked_text

    rendered_text = _render_markup(text, paragraph.get("markups") or [])
    match paragraph_type:
        case "H2":
            return f"## {rendered_text}"
        case "H3":
            return f"### {rendered_text}"
        case "H4":
            return f"#### {rendered_text}"
        case "BQ" | "PQ":
            return "\n".join(f"> {line}" for line in rendered_text.split("\n"))
        case _:
            return rendered_text


def _render_markup(text: str, markups: list[dict[str, Any]]) -> str:
    encoded_text = text.encode("utf-16-le")
    text_length = len(encoded_text) // 2
    openings: dict[int, list[tuple[int, int, str]]] = {}
    closings: dict[int, list[tuple[int, int, str]]] = {}

    for index, markup in enumerate(markups):
        markup_type = markup.get("type")
        match markup_type:
            case "STRONG":
                opening, closing = "**", "**"
            case "EM":
                opening, closing = "*", "*"
            case "CODE":
                opening, closing = "`", "`"
            case "A" if markup.get("href"):
                opening, closing = "[", f"]({markup['href']})"
            case _:
                continue

        start = max(0, min(int(markup.get("start") or 0), text_length))
        end = max(0, min(int(markup.get("end") or 0), text_length))
        if start >= end:
            continue

        selected_text = encoded_text[start * 2 : end * 2].decode("utf-16-le")
        left_trim = selected_text[: len(selected_text) - len(selected_text.lstrip())]
        right_trim = selected_text[len(selected_text.rstrip()) :]
        start += len(left_trim.encode("utf-16-le")) // 2
        end -= len(right_trim.encode("utf-16-le")) // 2
        if start >= end:
            continue

        openings.setdefault(start, []).append((end, index, opening))
        closings.setdefault(end, []).append((start, index, closing))

    rendered: list[str] = []
    position = 0
    for boundary in sorted(openings.keys() | closings.keys()):
        rendered.append(encoded_text[position * 2 : boundary * 2].decode("utf-16-le"))
        rendered.extend(
            closing for _, _, closing in sorted(closings.get(boundary, []), key=lambda item: (-item[0], -item[1]))
        )
        rendered.extend(
            opening for _, _, opening in sorted(openings.get(boundary, []), key=lambda item: (-item[0], item[1]))
        )
        position = boundary
    rendered.append(encoded_text[position * 2 :].decode("utf-16-le"))
    return "".join(rendered)


class MediumError(Exception):
    pass


__all__ = ["Medium", "MediumError", "MediumImage", "MediumPost"]
