import asyncio
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from yt_dlp import YoutubeDL

from ...config.config import GlobalConfig
from ...types import (
    DownloadError,
    DownloadResult,
    ParseError,
    ProgressCallback,
    VideoFile,
    VideoParseResult,
    VideoRef,
)
from .base import BaseParser

EXC = ProcessPoolExecutor()


def download_video(yto_params: dict, urls: list[str]) -> None:
    """在独立进程中下载视频"""
    try:
        with YoutubeDL(yto_params) as ydl:
            return ydl.download(urls)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise RuntimeError(error_msg) from None


class YtParser(BaseParser, register=False):
    """yt-dlp解析器"""

    async def _do_parse(self, raw_url: str) -> Union["YtVideoParseResult"]:
        video_info = await self._parse(raw_url)
        _d = {
            "title": video_info.title,
            "content": video_info.description,
            "raw_url": raw_url,
            "dl": video_info,
        }
        return YtVideoParseResult(
            video=VideoRef(
                url=raw_url,
                thumb_url=video_info.thumbnail,
                width=video_info.width,
                height=video_info.height,
                duration=video_info.duration,
            ),
            **_d,
        )

    async def _parse(self, url) -> "YtVideoInfo":
        try:
            dl = await asyncio.wait_for(asyncio.to_thread(self._extract_info, url), timeout=30)
        except TimeoutError as e:
            raise ParseError("解析视频信息超时") from e
        except Exception as e:
            raise ParseError(f"解析视频信息失败: {str(e)}") from e

        if dl.get("_type") and dl["_type"] == "playlist":  # type: ignore
            dl = dl["entries"][0]  # type: ignore
            url = dl["webpage_url"]
        title = dl["title"]
        duration = dl.get("duration", 0)
        thumbnail = dl["thumbnail"]
        description = dl["description"]
        width = dl.get("width", 0)
        height = dl.get("height", 0)
        return YtVideoInfo(
            raw_video_info=dl,
            title=title,
            description=description,
            thumbnail=thumbnail,
            duration=duration,
            url=url,
            width=width,
            height=height,
            paramss=self.params,
        )

    def _extract_info(self, url):
        params = self.params.copy()
        if self.cfg.proxy:
            params["proxy"] = self.cfg.proxy

        try:
            with YoutubeDL(params) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            raise RuntimeError(error_msg) from None

    @property
    def params(self) -> dict:
        params = {
            "format": "mp4+bestvideo[height<=1080]+bestaudio",
            "quiet": True,  # 不输出日志
            "noprogress": True,  # 不输出下载进度
            # "writethumbnail": True, # 下载缩略图
            # "postprocessors": [
            #     {
            #         "key": "FFmpegVideoConvertor",
            #         "preferedformat": "mp4", # 视频格式
            #     }
            # ],
            "playlist_items": "1",  # 分p列表默认解析第一个
        }
        return params


class YtVideoParseResult(VideoParseResult):
    def __init__(
        self,
        title,
        video=None,
        content=None,
        raw_url=None,
        dl: "YtVideoInfo" = None,
    ):
        """dl: yt-dlp解析结果"""
        self.dl = dl
        super().__init__(title=title, video=video, content=content, raw_url=raw_url)

    async def _do_download(
        self,
        *,
        output_dir: str | Path,
        callback: ProgressCallback = None,
        callback_args: tuple = (),
        proxy: str | None = None,
        headers: dict = None,
    ) -> "DownloadResult":
        paramss = self.dl.paramss.copy()
        if proxy:
            paramss["proxy"] = proxy

        paramss["outtmpl"] = f"{output_dir.joinpath('ytdlp_%(id)s')}.%(ext)s"

        if GlobalConfig.duration_limit and self.dl.duration > GlobalConfig.duration_limit:
            # 视频超过限制时长，获取最低画质
            paramss["format"] = "worstvideo* + worstaudio / worst"

        if callback:
            await callback(0, 1, "count", *callback_args)

        await self.__download(paramss)

        v = list(output_dir.glob("*.mp4")) or list(output_dir.glob("*.mkv")) or list(output_dir.glob("*.webm"))
        if not v:
            raise DownloadError("下载失败 -1")

        if callback:
            await callback(1, 1, "count", *callback_args)

        video_path = v[0]
        return DownloadResult(
            VideoFile(
                path=str(video_path),
                height=self.dl.height,
                width=self.dl.width,
                duration=self.dl.duration,
            ),
            output_dir,
        )

    async def __download(self, paramss: dict, count: int = 0) -> None:
        if count > 2:
            raise DownloadError("下载失败 -2")

        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(EXC, download_video, paramss, [self.dl.url]),
                timeout=300,
            )
        except TimeoutError as e:
            raise DownloadError("下载超时") from e
        except RuntimeError as e:
            error = str(e)
            if any(
                msg in error
                for msg in (
                    "Unable to download video subtitles",
                    "Requested format is not available",
                )
            ):
                paramss.pop("writeautomaticsub", None)
                await self.__download(paramss, count + 1)

        except Exception as e:
            raise DownloadError(f"下载失败: {str(e)}") from e


@dataclass
class YtVideoInfo:
    """raw_video_info: yt-dlp解析结果"""

    raw_video_info: dict
    title: str
    description: str
    thumbnail: str
    url: str
    """Youtube 链接, 非视频下载链接"""
    duration: int = 0
    width: int = 0
    height: int = 0
    paramss: dict = None
