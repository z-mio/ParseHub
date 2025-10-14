from dataclasses import dataclass
from enum import Enum
from typing import Union

import httpx

from ...config import GlobalConfig
from ...types import (
    Image,
    ImageParseResult,
    MultimediaParseResult,
    ParseError,
    Video,
    VideoParseResult,
)
from ..base.base import BaseParser


class DouyinParser(BaseParser):
    __platform_id__ = "douyin"
    __platform__ = "抖音|TikTok"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+douyin.com/.+|^(http(s)?://)?.+tiktok.com/.+"
    __redirect_keywords__ = ["v.douyin", "vt.tiktok"]
    __reserved_parameters__ = ["modal_id"]

    async def parse(self, url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        url = await self.get_raw_url(url)
        data = await self.parse_api(url)

        match data.type:
            case DYType.VIDEO:
                return await self.video_parse(url, data)
            case DYType.IMAGE:
                return await self.image_parse(url, data)
            case DYType.Multimedia:
                return await self.multimedia_parse(url, data)

    @staticmethod
    async def parse_api(url) -> "DYResult":
        if not GlobalConfig.douyin_api:
            raise ParseError("抖音解析API未配置")

        async with httpx.AsyncClient(timeout=15) as client:
            params = {"url": url, "minimal": False}
            try:
                response = await client.get(f"{GlobalConfig.douyin_api}/api/hybrid/video_data", params=params)
            except httpx.ReadTimeout as e:
                raise ParseError("抖音解析超时") from e
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

        def v_p(video_data: dict):
            """视频信息解析"""
            bit_rate = video_data.get("bit_rate")
            if not bit_rate:
                raise ParseError("抖音解析失败: 未获取到视频下载地址")
            bit_rate.sort(key=lambda x: x["quality_type"])
            bit_rate = bit_rate[0]

            video_url = bit_rate["play_addr"]["url_list"][0]
            thumb_url_list = video_data["cover"]["url_list"]
            thumb_url = thumb_url_list[-1] if thumb_url_list else None

            width = bit_rate["play_addr"]["width"]
            height = bit_rate["play_addr"]["height"]
            duration = bit_rate.get("duration", 0)
            return {
                "video_url": video_url,
                "thumb_url": thumb_url,
                "duration": duration,
                "width": width,
                "height": height,
            }

        if images := data.get("images"):
            if images[0].get("video"):
                multimedia = []
                for image in images:
                    if video := image.get("video"):
                        vpi = v_p(video)
                        multimedia.append(
                            Video(
                                vpi["video_url"],
                                thumb_url=vpi["thumb_url"],
                                width=vpi["width"],
                                height=vpi["height"],
                                duration=vpi["duration"],
                            )
                        )
                    else:
                        multimedia.append(Image(image["url_list"][-1]))

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
        elif image_post_info := data.get("image_post_info"):
            images = image_post_info.get("images")
            image_list = [Image(image["display_image"]["url_list"][-1]) for image in images]
            return DYResult(
                type=DYType.IMAGE,
                image_list=image_list,
                desc=desc,
                platform=platform,
            )
        else:
            vpi = v_p(data.get("video"))
            return DYResult(
                type=DYType.VIDEO,
                video=Video(
                    vpi["video_url"],
                    thumb_url=vpi["thumb_url"],
                    width=vpi["width"],
                    height=vpi["height"],
                    duration=vpi["duration"],
                ),
                desc=desc,
                platform=platform,
            )


__all__ = ["DouyinParser"]
