from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self, Union

from ... import ProgressCallback
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
        """获取并解析 TikTok API 结果"""
        crawler = TikTokWebCrawler(proxy=self.proxy, cookie=self.cookie)
        response = await crawler.parse(url)
        return TikTokApiResult.parse(response)

    @staticmethod
    def _build_video_result(result: "TikTokApiResult") -> VideoParseResult:
        """构建视频解析结果"""
        return TikTokVideoParseResult(
            title=result.desc,
            video=result.video,
        )

    @staticmethod
    def _build_image_result(result: "TikTokApiResult") -> ImageParseResult:
        """构建图片解析结果"""
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


def parse_video_info(video_data: dict) -> dict:
    """解析 TikTok 视频信息

    Args:
        video_data: TikTok API 返回的视频数据字典

    Returns:
        包含 video_url, thumb_url, duration, width, height 的字典

    Raises:
        ParseError: 未获取到视频下载地址时抛出
    """
    bit_rate_info = video_data.get("bitrateInfo")
    if not bit_rate_info:
        raise ParseError("TikTok 解析失败: 未获取到视频下载信`息")

    # 按分辨率降序排列，选择最高质量
    bit_rate_info.sort(
        key=lambda x: x.get("PlayAddr", {}).get("Width", 0) * x.get("PlayAddr", {}).get("Height", 0),
        reverse=True,
    )
    best_quality = bit_rate_info[0]

    play_addr = best_quality.get("PlayAddr", {})
    video_url_list = play_addr.get("UrlList", [])
    if not video_url_list:
        raise ParseError("抖音解析失败: 视频下载地址为空")

    video_url = next((u for u in video_url_list if "aweme" in u), None)
    thumb_url = video_data.get("cover")
    duration = video_data.get("duration", 0)
    width = video_data.get("width", 0)
    height = video_data.get("height", 0)

    return {
        "video_url": video_url,
        "thumb_url": thumb_url,
        "duration": duration,
        "width": width,
        "height": height,
    }


class TikTokMediaType(Enum):
    """TikTok 媒体类型"""

    VIDEO = "video"
    IMAGE = "image"  # 实况图片 + 图片


@dataclass
class TikTokApiResult:
    """TikTok API 解析结果"""

    type: TikTokMediaType
    video: VideoRef = None
    desc: str = ""
    image_list: list[ImageRef | LivePhotoRef] = None

    @classmethod
    def parse(cls, json_dict: dict) -> Self:
        """解析 TikTok API 响应

        Args:
            json_dict: TikTok API 返回的原始 JSON 数据

        Returns:
            TikTokApiResult 实例

        Raises:
            ParseError: 解析失败时抛出
        """
        data = json_dict.get("itemInfo", {}).get("itemStruct")
        if not data:
            raise ParseError("TikTok 解析失败: 未获取到作品详情")

        desc = data.get("desc", "")

        if image_post_info := data.get("imagePost"):
            return cls._parse_image_post(image_post_info, desc)
        else:
            return cls._parse_video(data, desc)

    @classmethod
    def _parse_image_post(cls, image_post_info: dict, desc: str) -> Self:
        """解析图片格式 (imagePost 字段)"""
        images = image_post_info.get("images", [])
        image_list = []

        for image in images:
            if video := image.get("video"):
                video_info = parse_video_info(video)
                image_list.append(
                    LivePhotoRef(
                        url=video_info["thumb_url"],
                        video_url=video_info["video_url"],
                        width=int(video_info["width"]),
                        height=int(video_info["height"]),
                        duration=int(video_info["duration"]) or 3,
                    )
                )
            else:
                url_list = image.get("image", {}).get("urlList", [])
                if url_list:
                    image_list.append(
                        ImageRef(
                            url=url_list[-1],
                            height=image.get("image", {}).get("height", 0),
                            width=image.get("image", {}).get("width", 0),
                        )
                    )

        return cls(
            type=TikTokMediaType.IMAGE,
            desc=desc,
            image_list=image_list,
        )

    @classmethod
    def _parse_video(cls, data: dict, desc: str) -> Self:
        """解析视频"""
        video_data = data.get("video")
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
