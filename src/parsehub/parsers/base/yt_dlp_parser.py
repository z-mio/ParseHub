import asyncio
from concurrent.futures import ProcessPoolExecutor

from ...utiles.img_host import ImgHost
import time
from dataclasses import dataclass
from typing import Union, Callable
from pathlib import Path
from yt_dlp import YoutubeDL

from .base import Parser
from ...config.config import DownloadConfig, GlobalConfig
from ...types import (
    VideoParseResult,
    ImageParseResult,
    Video,
    Subtitles,
    DownloadResult,
    ParseError,
)

EXC = ProcessPoolExecutor()


def download_video(yto_params: dict, urls: list[str]) -> None:
    """在独立进程中下载视频"""
    try:
        with YoutubeDL(yto_params) as ydl:
            return ydl.download(urls)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise ParseError(error_msg)


class YtParser(Parser):
    """yt-dlp解析器"""

    async def parse(
        self, url: str
    ) -> Union["YtVideoParseResult", "YtImageParseResult"]:
        url = await self.get_raw_url(url)
        video_info = await self._parse(url)
        _d = {
            "title": video_info.title,
            "desc": video_info.description,
            "raw_url": url,
            "dl": video_info,
        }
        if GlobalConfig.duration_limit and video_info.duration > 5400:
            return YtImageParseResult(photo=[video_info.thumbnail], **_d)
        else:
            return YtVideoParseResult(video=video_info.url, **_d)

    async def _parse(self, url, params=None) -> "YtVideoInfo":
        try:
            # dl = await asyncio.wait_for(
            #     loop.run_in_executor(EXC, extract_video_info, url, params), timeout=30
            # )
            dl = await asyncio.wait_for(
                asyncio.to_thread(self._extract_info, url, params), timeout=30
            )
        except asyncio.TimeoutError:
            raise ParseError("解析视频信息超时")
        except Exception as e:
            raise ParseError(f"解析视频信息失败: {str(e)}")

        if dl.get("_type"):
            dl = dl["entries"][0]
            url = dl["webpage_url"]
        title = dl["title"]
        duration = dl["duration"]
        thumbnail = dl["thumbnail"]
        description = dl["description"]

        return YtVideoInfo(
            raw_video_info=dl,
            title=title,
            description=description,
            thumbnail=thumbnail,
            duration=duration,
            url=url,
        )

    def _extract_info(self, url, params=None):
        with YoutubeDL(params or self.params) as ydl:
            return ydl.extract_info(url, download=False)

    # def hook(self, d):
    #     current = d.get("downloaded_bytes", 0)
    #     total = d.get("total_bytes", 0)
    #     if round(current * 100 / total, 1) % 25 == 0:
    #         self.loop.create_task(
    #             self.set_status(0, f"下 载 中...|{current * 100 / total:.0f}%")
    #         )

    @property
    def params(self) -> dict:
        params = {
            "format": "mp4+bestvideo[height<=1080]+bestaudio",
            "quiet": True,  # 不输出日志
            # "writethumbnail": True,  # 下载缩略图
            # "postprocessors": [
            #     {
            #         "key": "FFmpegVideoConvertor",
            #         "preferedformat": "mp4",  # 视频格式
            #     }
            # ],
            "playlist_items": "1",  # 分p列表默认解析第一个
            # "progress_hooks": [self.hook], # 进度回调
        }

        if self.cfg.proxy:
            params["proxy"] = self.cfg.proxy

        return params


class YtVideoParseResult(VideoParseResult):
    def __init__(
        self,
        title=None,
        video=None,
        desc=None,
        raw_url=None,
        dl: "YtVideoInfo" = None,
    ):
        """dl: yt-dlp解析结果"""
        self.dl = dl
        super().__init__(title=title, video=video, desc=desc, raw_url=raw_url)

    async def download(
        self,
        path: str | Path = None,
        callback: Callable = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        """下载视频"""
        if not self.media.is_url:
            return self.media

        # 创建保存目录
        dir_ = (config.save_dir if path is None else Path(path)).joinpath(
            f"{time.time_ns()}"
        )
        dir_.mkdir(parents=True, exist_ok=True)

        # 输出模板
        yto = YtParser().params
        if config.proxy:
            yto["proxy"] = config.proxy

        yto["outtmpl"] = f"{dir_.joinpath('ytdlp_%(id)s')}.%(ext)s"

        text = "下载合并中...请耐心等待..."
        if (
            GlobalConfig.duration_limit
            and self.dl.duration > GlobalConfig.duration_limit
        ):
            # 视频超过限制时长，获取最低画质
            text += f"\n视频超过{GlobalConfig.duration_limit}秒，获取最低画质"
            yto["format"] = "worstvideo* + worstaudio / worst"

        if callback:
            await callback(0, 0, text, *callback_args)

        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(EXC, download_video, yto, [self.media.path]),
                timeout=300,
            )
        except asyncio.TimeoutError:
            raise ParseError("下载超时")

        v = (
            list(dir_.glob("*.mp4"))
            or list(dir_.glob("*.mkv"))
            or list(dir_.glob("*.webm"))
        )
        if not v:
            raise ParseError("未获取到下载完成的视频")
        video_path = v[0]
        subtitles = (v := list(dir_.glob("*.ttml"))) and Subtitles().parse(v[0])
        try:
            thumb = await ImgHost(proxies=config.proxy).litterbox(self.dl.thumbnail)
        except Exception:
            thumb = None

        return DownloadResult(
            self,
            Video(path=str(video_path), subtitles=subtitles, thumb_url=thumb),
            dir_,
        )


class YtImageParseResult(ImageParseResult):
    def __init__(
        self, title="", photo=None, desc=None, raw_url=None, dl: "YtVideoInfo" = None
    ):
        """dl: yt-dlp解析结果"""
        self.dl = dl
        super().__init__(title=title, photo=photo, desc=desc, raw_url=raw_url)


@dataclass
class YtVideoInfo:
    """raw_video_info: yt-dlp解析结果"""

    raw_video_info: dict
    title: str
    description: str
    thumbnail: str
    duration: int
    url: str
