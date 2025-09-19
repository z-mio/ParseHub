import json
import math
from dataclasses import dataclass
from enum import Enum
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from ..config import GlobalConfig


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
        video_duration = video_height = video_width = 0
        match ppt:
            case PipixPostType.IMAGE:
                if cover := item.get("cover"):
                    images = [c["url"] for c in cover["download_list"]]
            case PipixPostType.VIDEO:
                video_download = item["video"]["video_download"]
                video_thumb = video_download["cover_image"]["download_list"][0]["url"]
                video = video_download["url_list"][0]["url"]
                video_duration = math.ceil(video_download["duration"])
                video_height = video_download["height"]
                video_width = video_download["width"]

        return PipixPost(
            ppt,
            content,
            images,
            video,
            video_thumb,
            video_duration,
            video_height,
            video_width,
        )


@dataclass
class PipixPost:
    type: "PipixPostType"
    content: str
    img_url: list | None = None
    video_url: str | None = None
    video_thumb: str | None = None
    video_duration: int | None = 0
    video_height: int | None = 0
    video_width: int | None = 0


class PipixPostType(Enum):
    IMAGE = 1
    VIDEO = 2
