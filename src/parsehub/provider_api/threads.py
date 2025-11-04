import json
import random
import re
import string
from dataclasses import dataclass
from enum import Enum

import httpx

from ..config.config import GlobalConfig


class ThreadsAPI:
    def __init__(self, proxy: str = None):
        self.proxy = proxy

    async def parse(self, url: str):
        lsd = self.random_lsd()
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "sec-fetch-site": "same-origin",
            "user-agent": GlobalConfig.ua,
            "x-fb-lsd": lsd,
        }

        data = {
            "route_url": f"/{self.get_username_by_url(url)}/post/{self.get_post_id_by_url(url)}/media",
            "routing_namespace": "barcelona_web",
            "__user": "0",
            "__a": "1",
            "__req": "m",
            "__comet_req": "29",
            "lsd": lsd,
        }

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.post("https://www.threads.com/ajax/route-definition", headers=headers, data=data)
            response.raise_for_status()
            jsonp = [json.loads(j.strip()) for j in response.text.strip().split("for (;;);") if j]
            return ThreadsPost.parse(jsonp)

    @staticmethod
    def get_username_by_url(url: str) -> str:
        u = re.search(r"/(@\w+)/post/", url)
        if not u:
            raise ValueError("从 URL 中获取用户名失败")
        return u[1]

    @staticmethod
    def get_post_id_by_url(url: str) -> str:
        p = re.search(r"/post/([\w-]+)", url)
        if not p:
            raise ValueError("从 URL 中获取帖子 ID 失败")
        return p[1]

    @staticmethod
    def random_lsd():
        return "".join(random.sample(string.ascii_letters + string.digits, 11))


class ThreadsMediaType(Enum):
    IMAGE = "image"
    VIDEO = "video"


@dataclass
class ThreadsMedia:
    type: ThreadsMediaType
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0


@dataclass
class ThreadsPost:
    content: str
    media: ThreadsMedia | list[ThreadsMedia] = None

    @classmethod
    def parse(cls, jsonp: list[dict]):
        content = ""
        media = []
        for j in jsonp:
            match j["__type"]:
                case "first_response":
                    content = cls._fetch_content(j)
                case "preloader":
                    if "BarcelonaLightboxDialogRootQueryRelayPreloader" in j.get("id"):
                        media = cls._fetch_media(j)
                case "last_response":
                    ...
        return cls(content=content, media=media)

    @staticmethod
    def _fetch_content(data: dict) -> str:
        payload = data["payload"]
        meta = payload.get("result", {}).get("exports", {}).get("meta")
        if not meta:
            raise Exception("获取内容失败")
        return meta["title"]

    @staticmethod
    def _fetch_media(data: dict):
        data = data.get("result", {}).get("result", {}).get("data", {}).get("data")
        if not data:
            return []

        def fn(d):
            media = []
            match d["media_type"]:
                case 1:  # 单张图片
                    image = d["image_versions2"]["candidates"][0]
                    media = ThreadsMedia(
                        type=ThreadsMediaType.IMAGE,
                        url=image["url"],
                        thumb_url=image["url"],
                        width=image["width"],
                        height=image["height"],
                    )
                case 2:  # 单个视频
                    thumb = d["image_versions2"]["candidates"][0]["url"]
                    video = d["video_versions"][0]["url"]
                    media = ThreadsMedia(
                        type=ThreadsMediaType.VIDEO,
                        url=video,
                        thumb_url=thumb,
                        width=d["original_width"],
                        height=d["original_height"],
                    )
                case 8:  # 多图/视频
                    carousel_media = d["carousel_media"]
                    media = []
                    for m in carousel_media:
                        if m["video_versions"]:
                            thumb = m["image_versions2"]["candidates"][0]["url"]
                            video = m["video_versions"][0]["url"]
                            media.append(
                                ThreadsMedia(
                                    type=ThreadsMediaType.VIDEO,
                                    url=video,
                                    thumb_url=thumb,
                                    width=m["original_width"],
                                    height=m["original_height"],
                                )
                            )
                        else:
                            image = m["image_versions2"]["candidates"][0]["url"]
                            media.append(
                                ThreadsMedia(
                                    type=ThreadsMediaType.IMAGE,
                                    url=image,
                                    thumb_url=image,
                                    width=m["original_width"],
                                    height=m["original_height"],
                                )
                            )
                case 19:  # 纯文本/外部链接
                    if linked_inline_media := d["text_post_app_info"]["linked_inline_media"]:
                        media = fn(linked_inline_media)
                    else:
                        media = []
                case _:
                    media = []
            return media

        return fn(data)
