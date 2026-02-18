import asyncio
import json
import re
from dataclasses import dataclass
from enum import Enum

import httpx
from bs4 import BeautifulSoup


class XHSAPI:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def __fetch_html(self, url: str):
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            return (await client.get(url, timeout=30)).text

    @staticmethod
    async def __extract_data(html: str):
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
        return data

    def __parse(self, data: dict):
        first_note_id = data["note"]["firstNoteId"]
        note = data["note"]["noteDetailMap"][first_note_id]["note"]
        title = note["title"]
        desc = note["desc"]
        return XHSPost(type=self.__get_post_type(note), title=title, desc=desc, media=self.__parse_media(note))

    @staticmethod
    def __get_post_type(note: dict):
        type_ = note["type"]

        match type_:
            case "video":
                return XHSPostType.VIDEO
            case "normal":
                return XHSPostType.IMAGE
            case _:
                return XHSPostType.UNKNOWN

    @staticmethod
    def __select_stream(stream: dict):
        if stream["h264"]:
            return stream["h264"]
        elif stream["av1"]:
            return stream["av1"]
        elif stream["h265"]:
            return stream["h265"]
        elif stream["h266"]:
            return stream["h266"]
        return None

    def __parse_media(self, note: dict):
        media_list = []
        il = note.get("imageList")
        video = note.get("video")
        if video:
            media = video["media"]
            stream = media["stream"]
            stream = self.__select_stream(stream)[0]
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
                    stream = self.__select_stream(i["stream"])[0]
                    image = XHSMedia(
                        XHSMediaType.LIVE_PHOTO,
                        thumb_url=i["urlDefault"],
                        url=stream["masterUrl"],
                        width=i["width"],
                        height=i["height"],
                    )
                else:
                    image = XHSMedia(
                        XHSMediaType.IMAGE,
                        url=i["urlDefault"],
                        thumb_url=i["urlPre"],
                        width=i["width"],
                        height=i["height"],
                    )
                media_list.append(image)
        return media_list

    async def extract(self, url: str):
        html = await self.__fetch_html(url)
        return self.__parse(await self.__extract_data(html))


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
    duration: int | None = None


@dataclass
class XHSPost:
    type: XHSPostType
    title: str
    desc: str
    media: list[XHSMedia] = None


if __name__ == "__main__":

    async def main():
        url = "https://www.xiaohongshu.com/explore/68fe2018000000000303a844?xsec_token=ABgAb-5vt3L-aTqeEjdxJP_ylf02hY5n2f-y75yMQWrUo=&xsec_source=pc_search&source=web_explore_feed"
        xhs = XHSAPI()
        print(await xhs.extract(url))

    asyncio.run(main())
