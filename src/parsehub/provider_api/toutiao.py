from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from ..utils.helpers import UA

_ID_RE = re.compile(r"toutiao\.com/(?:(?:article|video|w|group|item)/|a|i)(\d+)")
_INFO_API = "https://m.toutiao.com/i{}/info/v2/"
_VOD_API = "https://vod.bytedanceapi.com/?{}"


@dataclass
class ToutiaoImage:
    url: str
    width: int = 0
    height: int = 0


@dataclass
class ToutiaoVideo:
    url: str
    width: int = 0
    height: int = 0
    duration: int = 0
    thumb_url: str | None = None


@dataclass
class ToutiaoArticle:
    title: str
    markdown_content: str
    images: list[ToutiaoImage]
    videos: list[ToutiaoVideo]


@dataclass
class ToutiaoVideoPost:
    title: str
    video: ToutiaoVideo


@dataclass
class ToutiaoMicroPost:
    content: str
    images: list[ToutiaoImage]


class Toutiao:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, url: str) -> ToutiaoArticle | ToutiaoVideoPost | ToutiaoMicroPost:
        match = _ID_RE.search(url)
        if not match:
            raise ToutiaoError("不支持的今日头条链接")

        async with httpx.AsyncClient(proxy=self.proxy, timeout=30, headers={"User-Agent": UA}) as client:
            response = await client.get(_INFO_API.format(match.group(1)))
            response.raise_for_status()
            data = response.json().get("data")
            if data is None:
                raise ToutiaoError("内容不存在或已删除")

            if "thread" in data:
                return self._parse_micro_post(data["thread"])
            if data.get("biz_tag") == "图文":
                return await self._parse_article(client, data)
            if data.get("play_auth_token_v2"):
                video = await self._parse_video(
                    client,
                    data["play_auth_token_v2"],
                    duration=int(data.get("video_duration") or 0),
                    thumb_url=data.get("poster_url"),
                )
                return ToutiaoVideoPost(title=data.get("title") or "", video=video)
            return await self._parse_article(client, data)

    async def _parse_article(self, client: httpx.AsyncClient, data: dict[str, Any]) -> ToutiaoArticle:
        soup = BeautifulSoup(data.get("content") or "", "lxml")
        videos = []
        for video_box in soup.find_all("div", class_="tt-video-box"):
            token = str(video_box.get("data-token") or "")
            videos.append(await self._parse_video(client, token))
            video_box.decompose()

        converter = _ToutiaoMarkdownConverter()
        markdown_content = converter.convert(str(soup)).strip()
        return ToutiaoArticle(
            title=data.get("title") or "",
            markdown_content=markdown_content,
            images=[ToutiaoImage(url=url) for url in converter.images],
            videos=videos,
        )

    @staticmethod
    def _parse_micro_post(thread: dict[str, Any]) -> ToutiaoMicroPost:
        thread_base = thread.get("thread_base") or {}
        images = [
            ToutiaoImage(
                url=image["url"],
                width=int(image.get("width") or 0),
                height=int(image.get("height") or 0),
            )
            for image in thread_base.get("large_image_list", [])
            if image.get("url")
        ]
        return ToutiaoMicroPost(content=thread_base.get("content") or "", images=images)

    async def _parse_video(
        self,
        client: httpx.AsyncClient,
        token: str,
        *,
        duration: int = 0,
        thumb_url: str | None = None,
    ) -> ToutiaoVideo:
        token_data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        play_info_token = token_data["GetPlayInfoToken"]
        response = await client.get(_VOD_API.format(play_info_token))
        response.raise_for_status()
        payload = response.json()

        error = (payload.get("ResponseMetadata") or {}).get("Error")
        if error:
            if isinstance(error, dict):
                message = error.get("Message") or error.get("message") or error.get("ErrorMessage")
            else:
                message = error
            raise ToutiaoError(str(message or error))

        play_infos = payload["Result"]["Data"]["PlayInfoList"]
        best = max(
            play_infos,
            key=lambda item: (int(item.get("Height") or 0), int(item.get("Size") or 0)),
        )
        return ToutiaoVideo(
            url=best["MainPlayUrl"],
            width=int(best.get("Width") or 0),
            height=int(best.get("Height") or 0),
            duration=duration or int(best.get("Duration") or 0),
            thumb_url=thumb_url,
        )


class _ToutiaoMarkdownConverter(MarkdownConverter):
    def __init__(self) -> None:
        super().__init__(heading_style="ATX")
        self.images: list[str] = []

    def convert_img(self, el: Any, text: Any, parent_tags: Any) -> str:
        alt = el.attrs.get("alt") or ""
        src = el.attrs.get("src") or ""
        title = el.attrs.get("title") or ""
        if src:
            self.images.append(src)
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        return f"![{alt}]({src}{title_part})"


class ToutiaoError(Exception):
    pass


__all__ = [
    "Toutiao",
    "ToutiaoArticle",
    "ToutiaoError",
    "ToutiaoImage",
    "ToutiaoMicroPost",
    "ToutiaoVideo",
    "ToutiaoVideoPost",
]
