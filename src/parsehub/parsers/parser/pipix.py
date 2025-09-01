import json
from dataclasses import dataclass
from enum import Enum
from typing import Union
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from ..base.base import Parser
from ...config import GlobalConfig
from ...types import VideoParseResult, ImageParseResult, ParseError, Video


class PipixParser(Parser):
    __platform_id__ = "pipix"
    __platform__ = "皮皮虾"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?h5.pipix.com/(s|ppx/item)/.+"
    __redirect_keywords__ = ["/s/"]

    async def parse(self, url: str) -> Union["ImageParseResult", "VideoParseResult"]:
        try:
            ppx = await Pipix(self.cfg.proxy).parse(url)
        except Exception as e:
            raise ParseError("皮皮虾解析失败") from e

        if ppx.video_url:
            return VideoParseResult(
                title=ppx.content,
                video=Video(ppx.video_url, thumb_url=ppx.video_thumb),
                raw_url=url,
            )
        else:
            return ImageParseResult(title=ppx.content, photo=ppx.img_url, raw_url=url)


class Pipix:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, t_url) -> "PipixPost":
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            resp = await client.get(t_url, headers={"User-Agent": GlobalConfig.ua})
            resp.raise_for_status()
            return self._parse_data(resp.text)

    @staticmethod
    def _parse_data(data: str) -> "PipixPost":
        soup = BeautifulSoup(data, "lxml")
        raw_data = soup.find("script", {"id": "RENDER_DATA"}).text
        json_data = unquote(raw_data)
        data = json.loads(json_data)

        item = data.get("ppxItemDetail", {}).get("item")
        if not item:
            raise Exception("皮皮虾数据解析失败")

        ppt = PipixPostType(item["item_type"])
        content = item["content"]
        images = video = video_thumb = None
        match ppt:
            case PipixPostType.IMAGE:
                if cover := item.get("cover"):
                    images = [c["url"] for c in cover["download_list"]]
            case PipixPostType.VIDEO:
                video_download = item["video"]["video_download"]
                video_thumb = video_download["cover_image"]["download_list"][0]["url"]
                video = video_download["url_list"][0]["url"]

        return PipixPost(ppt, content, images, video, video_thumb)


@dataclass
class PipixPost:
    type: "PipixPostType"
    content: str
    img_url: list | None = None
    video_url: str | None = None
    video_thumb: str | None = None


class PipixPostType(Enum):
    IMAGE = 1
    VIDEO = 2


__all__ = ["PipixParser", "PipixPost"]
