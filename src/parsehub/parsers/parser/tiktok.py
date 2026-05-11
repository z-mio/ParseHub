from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self, Union

from ... import ProgressCallback
from ...config import GlobalConfig
from ...provider_api.tiktok import TikTokWebCrawler
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


class TikTokParser(BaseParser):
    __platform__ = Platform.TIKTOK
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+tiktok.com/(?!share/user|qishui).+"
    __redirect_keywords__ = ["vt.tiktok"]

    async def _do_parse(self, raw_url: str) -> Union["VideoParseResult", "ImageParseResult", "MultimediaParseResult"]:
        result = await self._fetch_api_result(raw_url)

        match result.type:
            case TikTokMediaType.VIDEO:
                return self._build_video_result(result)
            case TikTokMediaType.IMAGE:
                return self._build_image_result(result)

    async def _fetch_api_result(self, url: str) -> "TikTokApiResult":
        crawler = TikTokWebCrawler(proxy=self.proxy, cookie=self.cookie)
        try:
            response = await crawler.parse(url)
            return TikTokApiResult.parse(response)
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"TikTok 解析失败: {e}") from e

    @staticmethod
    def _build_video_result(result: "TikTokApiResult") -> VideoParseResult:
        return TikTokVideoParseResult(
            title=result.desc,
            video=result.video,
        )

    @staticmethod
    def _build_image_result(result: "TikTokApiResult") -> ImageParseResult:
        return ImageParseResult(
            title=result.desc,
            photo=result.image_list,
        )


class TikTokVideoParseResult(VideoParseResult):
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
            "User-Agent": GlobalConfig.ua,
            "Referer": "https://www.tiktok.com/",
        }
        return await super()._do_download(
            output_dir=output_dir,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            headers=headers,
        )


def first_url(data: dict | None) -> str | None:
    url_list = (data or {}).get("url_list") or (data or {}).get("UrlList") or []
    return next((url for url in url_list if url), None)


def as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def pick_cover(video_data: dict) -> str | None:
    for key in ("origin_cover", "cover", "dynamic_cover", "originCover", "dynamicCover"):
        cover_url = first_url(video_data.get(key))
        if cover_url:
            return cover_url
    cover = video_data.get("cover")
    return cover if isinstance(cover, str) else None


def parse_video_info(video_data: dict) -> dict:
    bit_rates = video_data.get("bit_rate") or video_data.get("bitrateInfo") or []
    candidates = []

    for bit_rate in bit_rates:
        play_addr = bit_rate.get("play_addr") or bit_rate.get("PlayAddr") or {}
        video_url = first_url(play_addr)
        if not video_url:
            continue

        width = as_int(play_addr.get("width") or play_addr.get("Width") or video_data.get("width"))
        height = as_int(play_addr.get("height") or play_addr.get("Height") or video_data.get("height"))
        bitrate = as_int(bit_rate.get("bit_rate") or bit_rate.get("Bitrate") or bit_rate.get("bitrate"))
        data_size = as_int(play_addr.get("data_size") or play_addr.get("DataSize") or bit_rate.get("data_size"))
        duration = as_int(play_addr.get("duration") or play_addr.get("Duration") or video_data.get("duration"))

        candidates.append(
            {
                "video_url": video_url,
                "thumb_url": pick_cover(video_data),
                "duration": duration,
                "width": width,
                "height": height,
                "quality": (width * height, bitrate, data_size),
            }
        )

    if not candidates:
        play_addr = video_data.get("play_addr") or video_data.get("playAddr") or {}
        video_url = first_url(play_addr)
        if video_url:
            width = as_int(play_addr.get("width") or video_data.get("width"))
            height = as_int(play_addr.get("height") or video_data.get("height"))
            candidates.append(
                {
                    "video_url": video_url,
                    "thumb_url": pick_cover(video_data),
                    "duration": as_int(play_addr.get("duration") or video_data.get("duration")),
                    "width": width,
                    "height": height,
                    "quality": (width * height, 0, 0),
                }
            )

    if not candidates:
        raise ParseError("TikTok 解析失败: 未获取到无水印视频下载地址")

    return max(candidates, key=lambda x: x["quality"])


class TikTokMediaType(Enum):
    VIDEO = "video"
    IMAGE = "image"


@dataclass
class TikTokApiResult:
    type: TikTokMediaType
    video: VideoRef = None
    desc: str = ""
    image_list: list[ImageRef | LivePhotoRef] = None

    @classmethod
    def parse(cls, json_dict: dict) -> Self:
        if not json_dict:
            raise ParseError("TikTok 解析失败: 未获取到作品详情")

        desc = json_dict.get("desc", "")
        image_post_info: dict = json_dict.get("image_post_info", {}) or json_dict.get("imagePost", {})
        if image_post_info:
            return cls._parse_image_post(image_post_info, desc)
        return cls._parse_video(json_dict, desc)

    @classmethod
    def _parse_image_post(cls, image_post_info: dict, desc: str) -> Self:
        image_list = []

        for image in image_post_info.get("images", []):
            display_image = image.get("display_image") or image.get("displayImage") or image.get("image") or {}
            url = first_url(display_image)
            if url:
                image_list.append(
                    ImageRef(
                        url=url,
                        height=as_int(display_image.get("height") or display_image.get("Height")),
                        width=as_int(display_image.get("width") or display_image.get("Width")),
                    )
                )

        if not image_list:
            raise ParseError("TikTok 解析失败: 未获取到无水印图文下载地址")

        return cls(
            type=TikTokMediaType.IMAGE,
            desc=desc,
            image_list=image_list,
        )

    @classmethod
    def _parse_video(cls, data: dict, desc: str) -> Self:
        video_data = data.get("video", {})
        if not video_data:
            raise ParseError("TikTok 解析失败: 未获取到视频数据")

        video_info = parse_video_info(video_data)

        return cls(
            type=TikTokMediaType.VIDEO,
            video=VideoRef(
                url=video_info["video_url"],
                thumb_url=video_info["thumb_url"],
                width=video_info["width"],
                height=video_info["height"],
                duration=video_info["duration"],
            ),
            desc=desc,
        )


__all__ = ["TikTokParser"]
