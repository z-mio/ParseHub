from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import httpx


class MediaType(Enum):
    VIDEO = "video"
    PHOTO = "photo"


@dataclass
class Media:
    url: str
    thumb_url: str
    type: MediaType


@dataclass
class ZuiYouPost:
    content: str
    media: list[Media]
    raw: dict

    @classmethod
    def parse(cls, json: dict):
        post = json["data"]["post"]
        content = post.get("content")
        videos = post.get("videos")
        imgs = post.get("imgs")
        media = []
        for img in imgs:
            id_ = img["id"]
            img_url = list(img["urls"].values())[-1]["urls"][-1]
            if img.get("video"):
                video_url = videos[str(id_)]["url"]
                media.append(Media(url=video_url, thumb_url=img_url, type=MediaType.VIDEO))
                continue
            media.append(Media(url=img_url, thumb_url=img_url, type=MediaType.PHOTO))

        return cls(content=content, media=media, raw=json)


@dataclass
class ZuiYou:
    def __init__(self, proxy: str = None):
        self.proxy = proxy
        self.api_url = "https://share.xiaochuankeji.cn/planck/share/post/detail_h5"

    async def parse(self, url: str) -> ZuiYouPost:
        pid = self.get_id_by_url(url)
        async with httpx.AsyncClient(proxy=self.proxy) as cli:
            result = await cli.post(self.api_url, json={"pid": pid})
        return ZuiYouPost.parse(result.json())

    @staticmethod
    def get_id_by_url(url: str) -> int:
        return (pid := dict(qc.split("=") for qc in urlparse(url).query.split("&")).get("pid")) and int(pid)
