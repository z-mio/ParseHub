from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from ..utils.helpers import UA

_TAG_RE = re.compile(
    r"\[(/?)(img|url|b|i|s|u|mask|quote|code|user|size|color|align|left|right|center|photo)(?:=([^\]]*))?\]",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"/(?:(subject/topic|group/topic)/(\d+)|blog/(\d+))(?:/|$)")
_API_BASE = "https://next.bgm.tv/p1"


@dataclass
class _BBCodeNode:
    tag: str
    value: str | None = None
    children: list[str | _BBCodeNode] = field(default_factory=list)


@dataclass
class BangumiPost:
    title: str
    markdown_content: str
    images: list[str]


class Bangumi:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, url: str) -> BangumiPost:
        match = _URL_RE.search(url)
        if not match:
            raise BangumiError("不支持的 Bangumi 链接")

        topic_type, topic_id, blog_id = match.groups()
        async with httpx.AsyncClient(proxy=self.proxy, timeout=30, headers={"User-Agent": UA}) as client:
            if blog_id:
                blog = await self._get_json(client, f"{_API_BASE}/blogs/{blog_id}")
                photos = await self._get_json(client, f"{_API_BASE}/blogs/{blog_id}/photos", params={"limit": 100})
                markdown_content, images = convert_bbcode(blog.get("content") or "")
                photo_urls = [
                    f"https://lain.bgm.tv/pic/photo/l/{photo['target'].lstrip('/')}"
                    for photo in photos.get("data", [])
                    if photo.get("target")
                ]
                content_images = set(images)
                extra_photo_urls = list(dict.fromkeys(url for url in photo_urls if url not in content_images))
                images = list(dict.fromkeys([*images, *photo_urls]))
                markdown_content += "".join(f"\n\n![]({url})" for url in extra_photo_urls)
                return BangumiPost(
                    title=blog.get("title") or "",
                    markdown_content=markdown_content,
                    images=images,
                )

            assert topic_type is not None and topic_id is not None
            api_type = "subjects" if topic_type == "subject/topic" else "groups"
            topic = await self._get_json(client, f"{_API_BASE}/{api_type}/-/topics/{topic_id}")
            replies = topic.get("replies") or []
            content = replies[0].get("content", "") if replies else ""
            markdown_content, images = convert_bbcode(content)
            return BangumiPost(
                title=topic.get("title") or "",
                markdown_content=markdown_content,
                images=images,
            )

    @staticmethod
    async def _get_json(client: httpx.AsyncClient, url: str, *, params: dict[str, int] | None = None) -> dict:
        response = await client.get(url, params=params)
        if not response.is_success:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            message = payload.get("message") if isinstance(payload, dict) else None
            raise BangumiError(str(message or f"HTTP {response.status_code}"))
        payload = response.json()
        if not isinstance(payload, dict):
            raise BangumiError(f"HTTP {response.status_code}: invalid JSON object")
        return payload


def convert_bbcode(content: str) -> tuple[str, list[str]]:
    content = content.replace("\r\n", "\n")
    content = re.sub(r"\((?:bgm|blake_|musume_)\d+\)", "", content, flags=re.IGNORECASE)

    root = _BBCodeNode("")
    stack = [root]
    position = 0
    for match in _TAG_RE.finditer(content):
        stack[-1].children.append(content[position : match.start()])
        closing, tag, value = match.groups()
        tag = tag.lower()
        if closing:
            for index in range(len(stack) - 1, 0, -1):
                if stack[index].tag == tag:
                    del stack[index:]
                    break
        else:
            node = _BBCodeNode(tag=tag, value=value)
            stack[-1].children.append(node)
            stack.append(node)
        position = match.end()
    stack[-1].children.append(content[position:])

    images: list[str] = []
    markdown_content = _render_nodes(root.children, images)
    return markdown_content.strip(), images


def _render_nodes(nodes: list[str | _BBCodeNode], images: list[str]) -> str:
    rendered: list[str] = []
    for node in nodes:
        if isinstance(node, str):
            rendered.append(node)
            continue

        body = _render_nodes(node.children, images)
        match node.tag:
            case "img":
                url = body.strip()
                if url:
                    images.append(url)
                    rendered.append(f"![]({url})")
            case "url" if node.value:
                rendered.append(f"[{body}]({node.value})")
            case "url":
                rendered.append(body)
            case "b":
                rendered.append(f"**{body}**")
            case "i":
                rendered.append(f"*{body}*")
            case "s":
                rendered.append(f"~~{body}~~")
            case "quote":
                quote = body.strip("\n")
                rendered.append("\n".join(f"> {line}" for line in quote.split("\n")) if quote else "")
            case "code":
                rendered.append(f"```\n{body.strip('\n')}\n```")
            case "user":
                rendered.append(f"@{body}")
            case _:
                rendered.append(body)
    return "".join(rendered)


class BangumiError(Exception):
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


__all__ = ["Bangumi", "BangumiError", "BangumiPost", "convert_bbcode"]
