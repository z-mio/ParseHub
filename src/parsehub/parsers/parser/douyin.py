from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self, Union

from ... import ProgressCallback
from ...provider_api.douyin import DouyinWebCrawler
from ...types import (
    DownloadResult,
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    MultimediaParseResult,
    ParseError,
    Platform,
    VideoParseResult,
    VideoRef,
)
from ..base.base import BaseParser


class DouyinParser(BaseParser):
    __platform__ = Platform.DOUYIN
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+douyin.com/(?!share/user|qishui).+"
    __redirect_keywords__ = ["v.douyin", "iesdouyin"]
    __reserved_parameters__ = ["modal_id"]

    async def _do_parse(self, raw_url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        data = await self.parse_api(raw_url)

        match data.type:
            case DYType.VIDEO:
                return await self.video_parse(data)
            case DYType.IMAGE:
                return await self.image_parse(data)

    async def parse_api(self, url) -> "DYResult":
        if not self.cookie:
            raise ParseError("抖音 Cookie 未配置")
        dwc = DouyinWebCrawler(proxy=self.proxy, cookie=self.cookie)
        response = await dwc.parse(url)
        return DYResult.parse(response)

    @staticmethod
    async def video_parse(result: "DYResult"):
        return DouyinVideoParseResult(
            title=result.desc,
            video=result.video,
        )

    @staticmethod
    async def image_parse(result: "DYResult"):
        return ImageParseResult(
            title=result.desc,
            photo=result.image_list,
        )


class DouyinVideoParseResult(VideoParseResult):
    async def _do_download(
        self,
        *,
        output_dir: str | Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
    ) -> "DownloadResult":
        headers = {
            # "User-Agent": GlobalConfig.ua,
            "Referer": "https://www.douyin.com/",
        }
        return await super()._do_download(
            output_dir=output_dir,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            headers=headers,
        )


class DYType(Enum):
    VIDEO = "video"
    IMAGE = "image"  # 实况图片 + 图片


@dataclass
class DYResult:
    type: DYType
    video: VideoRef = None
    desc: str = ""
    image_list: list[ImageRef | LivePhotoRef] = None

    @classmethod
    def parse(cls, json_dict: dict) -> Self:
        data = json_dict.get("aweme_detail")
        desc = data.get("desc")

        def v_p(video_data: dict):
            """视频信息解析"""
            bit_rate = video_data.get("bit_rate")
            if not bit_rate:
                raise ParseError("抖音解析失败: 未获取到视频下载地址")
            bit_rate.sort(key=lambda x: x["quality_type"])
            bit_rate = bit_rate[0]

            video_url = bit_rate["play_addr"]["url_list"][0]
            video_url = video_url.replace("playwm", "play")
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
            if any(i.get("video") for i in images):
                image_list = []
                for image in images:
                    if video := image.get("video"):
                        vpi = v_p(video)
                        image_list.append(
                            LivePhotoRef(
                                url=vpi["thumb_url"],
                                video_url=vpi["video_url"],
                                width=int(vpi["width"]),
                                height=int(vpi["height"]),
                                duration=int(vpi["duration"]) or 3,
                            )
                        )
                    else:
                        image_list.append(ImageRef(url=image["url_list"][-1]))

                return cls(
                    type=DYType.IMAGE,
                    desc=desc,
                    image_list=image_list,
                )
            else:
                image_list = [ImageRef(url=image["url_list"][-1]) for image in images]
                return cls(
                    type=DYType.IMAGE,
                    image_list=image_list,
                    desc=desc,
                )
        elif image_post_info := data.get("image_post_info"):
            images = image_post_info.get("images")
            image_list = [ImageRef(url=image["display_image"]["url_list"][-1]) for image in images]
            return cls(
                type=DYType.IMAGE,
                image_list=image_list,
                desc=desc,
            )
        else:
            vpi = v_p(data.get("video"))
            return cls(
                type=DYType.VIDEO,
                video=VideoRef(
                    url=vpi["video_url"],
                    thumb_url=vpi["thumb_url"],
                    width=vpi["width"],
                    height=vpi["height"],
                    duration=vpi["duration"],
                ),
                desc=desc,
            )


__all__ = ["DouyinParser"]
