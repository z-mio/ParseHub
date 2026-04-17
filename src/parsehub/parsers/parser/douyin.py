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
        result = await self._fetch_api_result(raw_url)

        match result.type:
            case DouyinMediaType.VIDEO:
                return self._build_video_result(result)
            case DouyinMediaType.IMAGE:
                return self._build_image_result(result)

    async def _fetch_api_result(self, url: str) -> "DouyinApiResult":
        """获取并解析抖音 API 结果"""
        if not self.cookie:
            raise ParseError("抖音 Cookie 未配置")

        crawler = DouyinWebCrawler(proxy=self.proxy, cookie=self.cookie)
        response = await crawler.parse(url)
        return DouyinApiResult.parse(response)

    @staticmethod
    def _build_video_result(result: "DouyinApiResult") -> VideoParseResult:
        """构建视频解析结果"""
        return DouyinVideoParseResult(
            title=result.desc,
            video=result.video,
        )

    @staticmethod
    def _build_image_result(result: "DouyinApiResult") -> ImageParseResult:
        """构建图片解析结果"""
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


def remove_video_watermark(url: str) -> str:
    """移除抖音视频水印标识 (playwm -> play)"""
    return url.replace("playwm", "play")


def parse_video_info(video_data: dict) -> dict:
    """解析抖音视频信息

    Args:
        video_data: 抖音 API 返回的视频数据字典

    Returns:
        包含 video_url, thumb_url, duration, width, height 的字典

    Raises:
        ParseError: 未获取到视频下载地址时抛出
    """
    bit_rates = video_data.get("bit_rate")
    if not bit_rates:
        raise ParseError("抖音解析失败: 未获取到视频下载地址")

    # 按分辨率降序排列，选择最高质量
    bit_rates.sort(
        key=lambda x: x.get("play_addr", {}).get("width", 0) * x.get("play_addr", {}).get("height", 0),
        reverse=True,
    )
    best_quality = bit_rates[0]

    play_addr = best_quality.get("play_addr", {})
    video_url_list = play_addr.get("url_list", [])
    if not video_url_list:
        raise ParseError("抖音解析失败: 视频下载地址为空")

    video_url = remove_video_watermark(video_url_list[0])

    cover = video_data.get("cover", {})
    thumb_url_list = cover.get("url_list", [])
    thumb_url = thumb_url_list[-1] if thumb_url_list else None

    return {
        "video_url": video_url,
        "thumb_url": thumb_url,
        "duration": best_quality.get("duration", 0),
        "width": play_addr.get("width", 0),
        "height": play_addr.get("height", 0),
    }


class DouyinMediaType(Enum):
    """抖音媒体类型"""

    VIDEO = "video"
    IMAGE = "image"  # 实况图片 + 图片


@dataclass
class DouyinApiResult:
    """抖音 API 解析结果"""

    type: DouyinMediaType
    video: VideoRef = None
    desc: str = ""
    image_list: list[ImageRef | LivePhotoRef] = None

    @classmethod
    def parse(cls, json_dict: dict) -> Self:
        """解析抖音 API 响应

        Args:
            json_dict: 抖音 API 返回的原始 JSON 数据

        Returns:
            DouyinApiResult 实例

        Raises:
            ParseError: 解析失败时抛出
        """
        data = json_dict.get("aweme_detail")
        if not data:
            raise ParseError("抖音解析失败: 未获取到作品详情")

        desc = data.get("desc", "")

        if images := data.get("images"):
            return cls._parse_images(images, desc)
        elif image_post_info := data.get("image_post_info"):
            return cls._parse_image_post_info(image_post_info, desc)
        else:
            return cls._parse_video(data, desc)

    @classmethod
    def _parse_images(cls, images: list[dict], desc: str) -> Self:
        """解析旧版图片格式 (images 字段)

        支持普通图片和实况照片 (LivePhoto)
        """
        has_live_photos = any(img.get("video") for img in images)

        if has_live_photos:
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
                    url_list = image.get("url_list", [])
                    if url_list:
                        image_list.append(
                            ImageRef(
                                url=url_list[-1],
                                height=image.get("height", 0),
                                width=image.get("width", 0),
                            )
                        )
        else:
            image_list = [
                ImageRef(
                    url=img["url_list"][-1],
                    height=img.get("height", 0),
                    width=img.get("width", 0),
                )
                for img in images
                if img.get("url_list")
            ]

        return cls(
            type=DouyinMediaType.IMAGE,
            desc=desc,
            image_list=image_list,
        )

    @classmethod
    def _parse_image_post_info(cls, image_post_info: dict, desc: str) -> Self:
        """解析新版图片格式 (image_post_info 字段)"""
        images = image_post_info.get("images", [])
        image_list = []

        for image in images:
            display_image = image.get("display_image", {})
            url_list = display_image.get("url_list", [])
            if url_list:
                image_list.append(
                    ImageRef(
                        url=url_list[-1],
                        height=display_image.get("height", 0),
                        width=display_image.get("width", 0),
                    )
                )

        return cls(
            type=DouyinMediaType.IMAGE,
            image_list=image_list,
            desc=desc,
        )

    @classmethod
    def _parse_video(cls, data: dict, desc: str) -> Self:
        """解析视频"""
        video_data = data.get("video")
        if not video_data:
            raise ParseError("抖音解析失败: 未获取到视频数据")

        video_info = parse_video_info(video_data)

        return cls(
            type=DouyinMediaType.VIDEO,
            video=VideoRef(
                url=video_info["video_url"],
                thumb_url=video_info["thumb_url"],
                width=video_info["width"],
                height=video_info["height"],
                duration=video_info["duration"],
            ),
            desc=desc,
        )


__all__ = ["DouyinParser"]
