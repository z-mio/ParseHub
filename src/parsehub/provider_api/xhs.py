from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import httpx
from bs4 import BeautifulSoup


class XHSAPI:
    def __init__(self, proxy: str | None = None, cookie: dict | None = None):
        self.proxy = proxy
        self.cookie = cookie

    async def __fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(proxy=self.proxy, cookies=self.cookie) as client:
            return (await client.get(url, timeout=30)).text

    @staticmethod
    async def __extract_data(html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        scripts = [
            script for script in soup.find_all("script") if script.text.lstrip().startswith("window.__INITIAL_STATE__")
        ]
        if not scripts:
            raise ValueError("No data found")
        script = scripts[0].text
        json_data = script.replace("window.__INITIAL_STATE__=", "")
        json_data = re.sub(r"\bundefined\b", "null", json_data)  # 清理js对象
        data = json.loads(json_data)
        return cast(dict[str, Any], data)

    def __parse(self, data: dict[str, Any]) -> XHSPost:
        if not data.get("note"):
            raise ValueError("该帖子需要登录后查看")
        first_note_id = data["note"]["firstNoteId"]
        note = data["note"]["noteDetailMap"][first_note_id]["note"]
        if not note:
            raise ValueError("未获取到内容, 该帖子可能需要登录后查看")

        title = note["title"]
        desc = note["desc"]
        return XHSPost(type=self.__get_post_type(note), title=title, desc=desc, media=self.__parse_media(note))

    @staticmethod
    def __get_post_type(note: dict[str, Any]) -> XHSPostType:
        type_ = note["type"]

        match type_:
            case "video":
                return XHSPostType.VIDEO
            case "normal":
                return XHSPostType.IMAGE
            case _:
                return XHSPostType.UNKNOWN

    @staticmethod
    def __select_stream(stream: dict[str, Any]) -> list[dict[str, Any]] | None:
        if stream["h264"]:
            return cast(list[dict[str, Any]], stream["h264"])
        elif stream["av1"]:
            return cast(list[dict[str, Any]], stream["av1"])
        elif stream["h265"]:
            return cast(list[dict[str, Any]], stream["h265"])
        elif stream["h266"]:
            return cast(list[dict[str, Any]], stream["h266"])
        return None

    def __parse_media(self, note: dict[str, Any]) -> list[XHSMedia]:
        media_list = []
        il = note.get("imageList") or []
        video = note.get("video")
        if video:
            media = video["media"]
            stream = media["stream"]
            selected_stream = self.__select_stream(stream)
            if not selected_stream:
                raise ValueError("未获取到视频流")
            stream = selected_stream[0]
            media_list.append(
                XHSMedia(
                    XHSMediaType.VIDEO,
                    url=stream["masterUrl"],
                    duration=stream["duration"],
                    height=stream["height"],
                    width=stream["width"],
                    thumb_url=il[0]["urlDefault"],
                )
            )
        else:
            for i in il:
                if i["livePhoto"]:
                    selected_stream = self.__select_stream(i["stream"])
                    if not selected_stream:
                        continue
                    stream = selected_stream[0]
                    image = XHSMedia(
                        XHSMediaType.LIVE_PHOTO,
                        thumb_url=self.get_raw_image_url(i["urlDefault"]),
                        url=stream["masterUrl"],
                        width=i["width"],
                        height=i["height"],
                    )
                else:
                    image = XHSMedia(
                        XHSMediaType.IMAGE,
                        url=self.get_raw_image_url(i["urlDefault"]),
                        thumb_url=i["urlPre"],
                        width=i["width"],
                        height=i["height"],
                    )
                media_list.append(image)
        return media_list

    async def extract(self, url: str) -> XHSPost:
        html = await self.__fetch_html(url)
        return self.__parse(await self.__extract_data(html))

    @staticmethod
    def get_trace_id(img_url: str) -> str:
        trace_id = img_url.split("/")[-1].split("!")[0]
        if "spectrum" in img_url:
            return "spectrum/" + trace_id
        if "note_pre_post_uhdr" in img_url:
            return "note_pre_post_uhdr/" + trace_id
        if "notes_pre_post" in img_url:
            return "notes_pre_post/" + trace_id
        return trace_id

    def get_raw_image_url(self, ime_url: str) -> str:
        """拼接无水印图片链接"""
        return f"http://sns-img-hw.xhscdn.com/{self.get_trace_id(ime_url)}"


class XHSMediaType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    LIVE_PHOTO = "livephoto"


class XHSPostType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


@dataclass
class XHSMedia:
    type: XHSMediaType
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0
    duration: int = 0


@dataclass
class XHSPost:
    type: XHSPostType
    title: str
    desc: str
    media: list[XHSMedia] | None = None


if __name__ == "__main__":

    async def main() -> None:
        url = "https://www.xiaohongshu.com/explore/68fe2018000000000303a844?xsec_token=ABgAb-5vt3L-aTqeEjdxJP_ylf02hY5n2f-y75yMQWrUo=&xsec_source=pc_search&source=web_explore_feed"
        xhs = XHSAPI()
        print(await xhs.extract(url))

    asyncio.run(main())
