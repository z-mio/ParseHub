from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import httpx
from bs4 import BeautifulSoup
from xhshow import Xhshow

from ..errors import ContentUnavailableError, ParseError
from ..utils.helpers import UA

PC_HEADERS = {
    "User-Agent": UA,
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp"
    ",image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
}
# 手机 UA 配 Chrome 的 accept 会被跳到验证码页
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
ACTIVATE_URI = "/api/sns/web/v1/login/activate"


class XHSAPI:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy
        self.xhshow = Xhshow()

    async def __fetch_html(self, url: str, headers: dict[str, str], cookie: dict | None = None) -> str:
        async with httpx.AsyncClient(proxy=self.proxy, cookies=cookie, follow_redirects=True) as client:
            try:
                result = await client.get(url, headers=headers, timeout=30)
            except httpx.HTTPError as e:
                raise ParseError(f"请求失败: {e!r}") from e
            if "/login" in str(result.url):
                raise ParseError("该帖子需要登录后查看")
            elif "/404/sec" in str(result.url):
                raise ParseError("被小红书风控拦截")
            elif "/404" in str(result.url):
                raise ContentUnavailableError("帖子不存在")
            return result.text

    async def new_session(self) -> dict[str, str]:
        """获取游客 web_session"""
        a1 = self.xhshow.generate_a1()
        cookies = {"a1": a1, "webId": self.xhshow.generate_web_id(a1), "xsecappid": "xhs-pc-web"}
        payload = {"client_public_key_base64": base64.b64encode(os.urandom(32)).decode()}
        headers = self.xhshow.sign_headers_post(ACTIVATE_URI, cookies, payload=payload)
        headers.update(
            {
                "User-Agent": UA,
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": "https://www.xiaohongshu.com",
                "Referer": "https://www.xiaohongshu.com/",
            }
        )
        async with httpx.AsyncClient(proxy=self.proxy, cookies=cookies, timeout=30) as client:
            try:
                result = await client.post(
                    f"https://edith.xiaohongshu.com{ACTIVATE_URI}",
                    headers=headers,
                    content=self.xhshow.build_json_body(payload),
                )
            except httpx.HTTPError as e:
                raise ParseError(f"获取游客 session 失败: {e!r}") from e
        if not (web_session := result.cookies.get("web_session")):
            raise ParseError(f"获取游客 session 失败: {result.status_code} {result.text}")
        return {"web_session": web_session}

    @staticmethod
    async def __extract_data(html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        scripts = [
            script for script in soup.find_all("script") if script.text.lstrip().startswith("window.__INITIAL_STATE__")
        ]
        if not scripts:
            raise ParseError("No data found")
        script = scripts[0].text
        json_data = script.replace("window.__INITIAL_STATE__=", "")
        json_data = re.sub(r"\bundefined\b", "null", json_data)  # 清理js对象
        data = json.loads(json_data)
        return cast(dict[str, Any], data)

    def __parse(self, data: dict[str, Any]) -> XHSPost:
        if h5_data := data.get("noteData"):
            note = (h5_data.get("data") or {}).get("noteData")
        elif pc_data := data.get("note"):
            note = (pc_data["noteDetailMap"].get(pc_data["firstNoteId"]) or {}).get("note")
        else:
            raise ParseError("该帖子需要登录后查看")
        if not note:
            raise ParseError("未获取到内容, 该帖子可能需要登录后查看")

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

    @staticmethod
    def __image_url(image: dict[str, Any]) -> str:
        return cast(str, image.get("urlDefault") or image["url"])

    def __image_thumb_url(self, image: dict[str, Any]) -> str:
        if url := image.get("urlPre"):
            return cast(str, url)
        for info in image.get("infoList") or []:
            if info.get("imageScene") == "H5_PRV":
                return cast(str, info["url"])
        return self.__image_url(image)

    def __parse_media(self, note: dict[str, Any]) -> list[XHSMedia]:
        media_list = []
        il = note.get("imageList") or []
        video = note.get("video")
        if video:
            media = video["media"]
            stream = media["stream"]
            selected_stream = self.__select_stream(stream)
            if not selected_stream:
                raise ParseError("未获取到视频流")
            stream = selected_stream[0]
            media_list.append(
                XHSMedia(
                    XHSMediaType.VIDEO,
                    url=stream["masterUrl"],
                    duration=stream["duration"],
                    height=stream["height"],
                    width=stream["width"],
                    thumb_url=self.__image_url(il[0]),
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
                        thumb_url=self.get_raw_image_url(self.__image_url(i)),
                        url=stream["masterUrl"],
                        width=i["width"],
                        height=i["height"],
                    )
                else:
                    image = XHSMedia(
                        XHSMediaType.IMAGE,
                        url=self.get_raw_image_url(self.__image_url(i)),
                        thumb_url=self.__image_thumb_url(i),
                        width=i["width"],
                        height=i["height"],
                    )
                media_list.append(image)
        return media_list

    async def extract(self, url: str, headers: dict[str, str], cookie: dict | None = None) -> XHSPost:
        html = await self.__fetch_html(url, headers, cookie)
        return self.__parse(await self.__extract_data(html))

    @staticmethod
    def get_trace_id(img_url: str) -> str:
        match = re.search(r"/[a-f0-9]{32}/(.*)/([^/!]+)(?:!.*)?", img_url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"

        match = re.search(r"/([^/!]+)(?:!.*)?$", img_url)
        if match:
            return match.group(1)
        return img_url

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
        url = ""
        xhs = XHSAPI()
        print(await xhs.extract(url, PC_HEADERS))

    asyncio.run(main())
