from dataclasses import dataclass
from typing import Union

import httpx
from enum import Enum
from ..base.base import Parser
from ...types import (
    VideoParseResult,
    ImageParseResult,
    ParseError,
    Video,
    Image,
    MultimediaParseResult,
)


class DouyinParser(Parser):
    __platform__ = "抖音|TikTok"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+douyin.com/.+|^(http(s)?://)?.+tiktok.com/.+"
    __redirect_keywords__ = ["v.douyin", "vt.tiktok"]

    async def parse(
        self, url: str
    ) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        url = await self.get_raw_url(url)
        data = await self.parse_api(url)

        match data.type:
            case DYType.VIDEO:
                return await self.video_parse(url, data)
            case DYType.IMAGE:
                return await self.image_parse(url, data)
            case DYType.Multimedia:
                return await self.multimedia_parse(url, data)
            case _:
                raise ValueError(f"未知类型: {data.type}")

    async def parse_api(self, url) -> "DYResult":
        if not self.cfg.douyin_api:
            raise ParseError("抖音解析API未配置")

        async with httpx.AsyncClient(timeout=10) as client:
            params = {"url": url, "minimal": False}
            response = await client.get(
                f"{self.cfg.douyin_api}/api/hybrid/video_data", params=params
            )
        if response.status_code != 200:
            raise ParseError("抖音解析失败")
        return DYResult.parse(url, response.json())

    @staticmethod
    async def video_parse(url, result: "DYResult"):
        return VideoParseResult(
            raw_url=url,
            title=result.desc,
            video=result.video,
        )

    @staticmethod
    async def image_parse(url, result: "DYResult"):
        return ImageParseResult(
            raw_url=url,
            title=result.desc,
            photo=result.image_list,
        )

    @staticmethod
    async def multimedia_parse(url, result: "DYResult"):
        return MultimediaParseResult(
            raw_url=url,
            title=result.desc,
            media=result.multimedia,
        )


class DYType(Enum):
    VIDEO = "video"
    IMAGE = "image"
    Multimedia = "multimedia"


@dataclass
class DYResult:
    type: DYType
    platform: str
    video: Video = None
    desc: str = ""
    image_list: list[Image] = None
    multimedia: list[Video | Image] = None

    @staticmethod
    def parse(url: str, json_dict: dict):
        platform = "douyin" if "douyin" in url else "tiktok"
        data = json_dict.get("data")
        desc = data.get("desc")

        def fn(video_data: dict):
            video = video_data.get("bit_rate")
            if not video:
                raise ParseError("抖音解析失败: 未获取到视频下载地址")
            video.sort(key=lambda x: x["quality_type"])
            video = video[0]["play_addr"]["url_list"][-1]
            thumb = video_data["cover"]["url_list"][-1]
            return video, thumb

        if images := data.get("images"):
            if images[0].get("video"):
                video_list = [fn(image["video"]) for image in images]
                multimedia = [Video(v[0], thumb_url=v[1]) for v in video_list]
                return DYResult(
                    type=DYType.Multimedia,
                    desc=desc,
                    multimedia=multimedia,
                    platform=platform,
                )
            else:
                image_list = [Image(image["url_list"][-1]) for image in images]
                return DYResult(
                    type=DYType.IMAGE,
                    image_list=image_list,
                    desc=desc,
                    platform=platform,
                )
        else:
            v = fn(data.get("video"))
            return DYResult(
                type=DYType.VIDEO,
                video=Video(v[0], thumb_url=v[1]),
                desc=desc,
                platform=platform,
            )
