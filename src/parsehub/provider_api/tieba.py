import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Self

import httpx


class TieBa:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, url: str) -> "TieBaPost":
        data = await self.fetch_post_data(url)
        return TieBaPost.parse(data)

    @staticmethod
    def gen_sign(params: dict):
        items = sorted(params.items())
        base_str = "".join([f"{k}={v}" for k, v in items])
        salt = "36770b1f34c9bbf2e7d1a99d2b82fa9e"
        return hashlib.md5((base_str + salt).encode("utf-8")).hexdigest()

    async def fetch_tbs(self) -> str:
        async with httpx.AsyncClient(proxy=self.proxy) as cli:
            result = await cli.get("http://tieba.baidu.com/dc/common/tbs")
            result.raise_for_status()
        result = result.json()
        if tbs := result.get("tbs"):
            return tbs
        raise TieBaError("获取 tbs 失败")

    @staticmethod
    def get_kz(url: str) -> str:
        if match := re.search(r"/p/(\d+)", url):
            return match.group(1)
        raise ValueError("无法从 URL 中提取帖子 ID")

    async def fetch_post_data(self, url: str) -> dict:
        kz = self.get_kz(url)
        tbs = await self.fetch_tbs()
        data = {
            "pn": "1",
            "lz": "0",
            "r": "2",
            "mark_type": "0",
            "back": "0",
            "fr": "personalize_page",
            "kz": kz,
            "session_request_times": "1",
            "tbs": tbs,
            "subapp_type": "pc",
            "_client_type": "20",
        }
        data["sign"] = self.gen_sign(data)
        async with httpx.AsyncClient(proxy=self.proxy, timeout=30) as cli:
            result = await cli.post("https://tieba.baidu.com/c/f/pb/page_pc", data=data)
            result.raise_for_status()
            result = result.json()
        if result["error_code"]:
            raise TieBaError(em if (em := result["error_msg"]) else "获取帖子内容失败")
        return result


class TieBaPostType(Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"


@dataclass
class TieBaVideo:
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0
    duration: int = 0


@dataclass
class TieBaPhoto:
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0


@dataclass
class TieBaPost:
    type: TieBaPostType
    title: str
    content: str
    media: list[TieBaPhoto] | TieBaVideo | None = None

    @classmethod
    def parse(cls, data: dict) -> Self:
        thread = data["thread"]
        origin_thread_info = thread["origin_thread_info"]

        # title
        title = origin_thread_info["title"]

        # content
        origin_content = origin_thread_info["content"]
        content_list: list[str] = []
        for oc in origin_content:
            oc_type = oc["type"]
            match oc_type:
                case 0:
                    content_list.append(oc["text"])
        content = "\n".join(content_list)

        # media
        media = []
        if origin_media := origin_thread_info.get("media"):
            post_type = TieBaPostType.PHOTO
            for om in origin_media:
                media.append(
                    TieBaPhoto(
                        url=om["big_pic"],
                        thumb_url=om["small_pic"],
                        width=om["width"],
                        height=om["height"],
                    )
                )

        elif video_info := thread.get("video_info"):
            post_type = TieBaPostType.VIDEO
            media.append(
                TieBaVideo(
                    url=video_info["video_url"],
                    thumb_url=video_info["thumbnail_url"],
                    width=video_info["video_width"],
                    height=video_info["video_height"],
                    duration=video_info["video_duration"],
                )
            )
        else:
            post_type = TieBaPostType.PHOTO

        m = media[0] if post_type == TieBaPostType.VIDEO else media if media else None
        return TieBaPost(
            type=post_type,
            title=title,
            content=content,
            media=m,
        )


class TieBaError(Exception):
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)
