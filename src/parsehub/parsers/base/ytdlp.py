import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from loguru import logger
from yt_dlp import YoutubeDL

from ...types import (
    AnyParseResult,
    DownloadError,
    DownloadResult,
    ParseError,
    ProgressCallback,
    VideoFile,
    VideoParseResult,
    VideoRef,
)
from .base import BaseParser


def switch_ytdlp_proxy(ydl: YoutubeDL, proxy: str | None) -> None:
    """切换同一个 YoutubeDL 实例后续请求使用的代理。"""
    ydl.params["proxy"] = proxy or ""

    # proxies 是 cached_property，必须清掉，否则仍会使用解析阶段的 proxy map
    ydl.__dict__.pop("proxies", None)

    # _request_director 也是 cached_property，内部 handler 初始化时已经绑定旧 proxies
    director = ydl.__dict__.pop("_request_director", None)
    if director is not None:
        director.close()


@logger.catch
def download_video(yto_params: dict[str, Any], url: str, proxy: str | None = None) -> None:
    """在独立线程中下载视频"""
    try:
        with YoutubeDL(yto_params) as ydl:
            info = ydl.extract_info(url, download=False)
            switch_ytdlp_proxy(ydl, proxy)
            ydl.process_ie_result(info, download=True)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise RuntimeError(error_msg) from None


class MonotonicDownloadProgress:
    def __init__(
        self, emit: Callable[[float], None], *, start: float = 0.0, end: float = 100.0, min_step: float = 0.1
    ) -> None:
        self.emit = emit
        self.start = start
        self.end = end
        self.min_step = min_step
        self.current = start

    def __call__(self, d: dict[str, Any]) -> None:
        status = d.get("status")

        if status == "downloading":
            percent = self._download_percent(d)
            if percent is None:
                return

            mapped = self.start + percent * (self.end - self.start) / 100

            if mapped >= self.current + self.min_step:
                self.current = mapped
                self.emit(round(self.current, 1))

        elif status == "finished":
            if self.current < self.end:
                self.current = self.end
                self.emit(round(self.current, 1))

    @staticmethod
    def _download_percent(d: dict) -> float | None:
        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        if downloaded == total == 1024:
            return None

        if total > 0:
            return min(downloaded / total * 100, 100)

        # 分片下载有时没有稳定总大小，但有 frag 进度；作为兜底
        frag_index = d.get("fragment_index")
        frag_count = d.get("fragment_count")
        if isinstance(frag_index, int | float) and isinstance(frag_count, int | float) and frag_count:
            return min(float(frag_index) / float(frag_count) * 100, 100.0)

        return None


class YtParser(BaseParser, register=False):
    """yt-dlp解析器"""

    async def _do_parse(self, raw_url: str) -> AnyParseResult:
        video_info = await self._parse(raw_url)
        return YtVideoParseResult(
            dl=video_info,
            title=video_info.title,
            content=video_info.description,
            video=VideoRef(
                url=raw_url,
                thumb_url=video_info.thumbnail,
                width=video_info.width,
                height=video_info.height,
                duration=video_info.duration,
            ),
        )

    async def _parse(self, url: str) -> "YtVideoInfo":
        try:
            dl = await asyncio.wait_for(asyncio.to_thread(self._extract_info, url), timeout=30)
        except TimeoutError as e:
            raise ParseError("解析视频信息超时") from e
        except Exception as e:
            raise ParseError(f"解析视频信息失败: {str(e)}") from e

        if dl.get("_type") and dl["_type"] == "playlist":
            dl = dl["entries"][0]
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
            proxy=self.proxy,
        )

    def _extract_info(self, url: str) -> dict[str, Any]:
        params = self.params.copy()
        if self.proxy:
            params["proxy"] = self.proxy

        try:
            with YoutubeDL(params) as ydl:
                return cast(dict[str, Any], ydl.extract_info(url, download=False))
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            raise RuntimeError(error_msg) from None

    @property
    def params(self) -> dict[str, Any]:
        params = {
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
        dl: "YtVideoInfo",
        title: str | None,
        video: VideoRef | None = None,
        content: str | None = None,
    ):
        """dl: yt-dlp解析结果"""
        self.dl = dl
        super().__init__(title=title, video=video, content=content)

    async def _do_download(
        self,
        *,
        output_dir: Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
        connections: int = 4,
    ) -> "DownloadResult":
        if callback_kwargs is None:
            callback_kwargs = {}
        output_dir_path = Path(output_dir)

        paramss = self.dl.paramss.copy()
        if self.dl.proxy:
            paramss["proxy"] = self.dl.proxy

        paramss["outtmpl"] = f"{output_dir_path.joinpath(self.name)}.%(ext)s"
        paramss["concurrent_fragment_downloads"] = connections  # 多线程下载

        if callback:
            loop = asyncio.get_running_loop()

            def _callback(count: float) -> None:
                asyncio.run_coroutine_threadsafe(
                    callback(int(count), 100, "bytes", *callback_args, **callback_kwargs), loop
                )

            progress = MonotonicDownloadProgress(
                _callback,
                start=0,
                end=99,
            )
            paramss["progress_hooks"] = [progress]

        await self._run_download(paramss, proxy=proxy)

        v = (
            list(output_dir_path.glob("*.mp4"))
            or list(output_dir_path.glob("*.mkv"))
            or list(output_dir_path.glob("*.webm"))
        )
        if not v:
            raise DownloadError("下载失败 -1")

        if callback:
            await callback(100, 100, "bytes", *callback_args, **callback_kwargs)

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

    async def _run_download(self, paramss: dict[str, Any], count: int = 0, *, proxy: str | None = None) -> None:
        if count > 2:
            raise DownloadError("下载失败 -2")

        try:
            await asyncio.to_thread(download_video, paramss, self.dl.url, proxy=proxy)
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
                await self._run_download(paramss, count + 1, proxy=proxy)

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
    paramss: dict
    """Youtube 链接, 非视频下载链接"""
    duration: int = 0
    width: int = 0
    height: int = 0
    proxy: str | None = None
    """解析时用的代理"""
