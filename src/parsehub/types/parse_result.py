import asyncio
import os
import shutil
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage

from ..config.config import DownloadConfig, SummaryConfig
from ..tools import LLM, Transcriptions
from ..utiles.download_file import download_file
from ..utiles.utile import image_proces, progress, video_to_png
from . import DownloadError
from .media import Image, Media, MediaT, Video
from .subtitles import Subtitle, Subtitles
from .summary_result import SummaryResult

T = TypeVar("T", bound="ParseResult")


class ParseResult:
    """解析结果基类"""

    def __init__(
        self,
        title: str,
        media: list[MediaT] | MediaT,
        desc: str = "",
        raw_url: str = None,
    ):
        """
        :param title: 标题
        :param media: 媒体下载链接
        :param desc: 正文
        :param raw_url: 原始帖子链接
        """
        self.title = (title or "").strip()
        self.media = media
        self.desc = (desc or "").strip()
        self.raw_url = raw_url

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(title={self.title or "''"}, desc={self.desc or "''"}, raw_url={self.raw_url})"
        )

    async def download(
        self,
        path: str | Path = None,
        callback: Callable[[int, int, str | None, tuple], Awaitable[None]] = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> "DownloadResult":
        """
        :param path: 保存路径
        :param callback: 下载进度回调函数
        :param callback_args: 下载进度回调函数参数
        :param config: 下载配置
        :return: DownloadResult

        .. note::
        下载进度回调函数签名: async def callback(current: int, total: int, status: str|None, *args) -> None:
        status: 进度或其他状态信息
        """
        save_dir = Path(path) if path else config.save_dir
        if isinstance(self.media, list):
            path_list = []
            op = save_dir.joinpath(f"{time.time_ns()}")
            for i, media in enumerate(self.media):
                if not media.is_url:
                    path_list.append(media)
                    continue
                try:
                    f = await download_file(
                        media.path,
                        f"{op}/{i}.{media.ext}",
                        proxies=config.proxy,
                        headers=config.headers,
                    )
                except Exception as e:
                    shutil.rmtree(op)
                    raise DownloadError(f"下载失败: {e}") from e
                n_m = media.__class__(**vars(media))
                n_m.path = f
                path_list.append(n_m)

                if callback:
                    await callback(
                        len(path_list),
                        len(self.media),
                        progress(len(path_list), len(self.media), "数量"),
                        *callback_args,
                    )
            return DownloadResult(self, path_list, op)
        else:
            if not self.media.is_url:
                return self.media

            async def _callback(current, total, *args):
                await callback(
                    current,
                    total,
                    progress(current, total, "百分比"),
                    *args,
                )

            try:
                r = await download_file(
                    self.media.path,
                    save_dir / f"{time.time_ns()}.{self.media.ext}",
                    headers=config.headers,
                    proxies=config.proxy,
                    progress=_callback if callback else None,
                    progress_args=callback_args,
                )
            except Exception as e:
                raise DownloadError(f"下载失败: {e}") from e

            # 小于10KB为下载失败
            if not os.stat(r).st_size > 10 * 1024:
                os.remove(r)
                raise DownloadError("下载失败")
            n_m = self.media.__class__(**vars(self.media))
            n_m.path = r
            return DownloadResult(self, n_m)

    async def summary(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        provider: Literal["openai"] = None,
        transcriptions_provider: str = None,
        prompt: str = None,
        download_config: DownloadConfig = DownloadConfig(),
    ) -> "SummaryResult":
        """总结解析结果
        :param api_key: API密钥
        :param base_url: API地址
        :param model: 语言模型
        :param provider: 语言模型提供商
        :param transcriptions_provider: 语音转文本提供商
        :param prompt: 提示词
        :param download_config: 下载配置
        """
        dr = await self.download(config=download_config)
        sr = await dr.summary(api_key, base_url, model, provider, prompt, transcriptions_provider)
        dr.delete()
        return sr


class VideoParseResult(ParseResult):
    def __init__(
        self,
        title: str = "",
        video: str | Video = None,
        raw_url: str = None,
        desc: str = "",
    ):
        video = Video(video) if isinstance(video, str) else video
        super().__init__(
            title=title,
            media=video,
            desc=desc,
            raw_url=raw_url,
        )


class ImageParseResult(ParseResult):
    def __init__(
        self,
        title: str = "",
        photo: list[str | Image] = None,
        desc: str = "",
        raw_url: str = None,
    ):
        photo = [Image(p) if isinstance(p, str) else p for p in photo]
        super().__init__(title=title, media=photo, desc=desc, raw_url=raw_url)


class MultimediaParseResult(ParseResult):
    def __init__(
        self,
        title: str = "",
        media: list[Media] = None,
        desc: str = "",
        raw_url: str = None,
    ):
        super().__init__(title=title, media=media, desc=desc, raw_url=raw_url)


class DownloadResult[T]:
    def __init__(self, parse_result: T, media: list[MediaT] | MediaT, save_dir: str | Path = None):
        """
        下载结果
        :param parse_result: 解析结果
        :param media: 本地媒体路径
        :param save_dir: 保存目录
        """
        self.pr = parse_result
        """解析结果"""
        self.media = media
        self.save_dir = Path(save_dir).resolve() if save_dir else None

    def exists(self) -> bool:
        """是否存在本地文件"""
        if isinstance(self.media, list):
            return all(m.exists() for m in self.media)
        else:
            return self.media.exists()

    async def summary(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        provider: Literal["openai"] = None,
        prompt: str = None,
        transcriptions_provider: Literal["openai", "fast_whisper", "azure"] = None,
        transcriptions_api_key: str = None,
        transcriptions_base_url: str = None,
    ) -> "SummaryResult":
        """总结解析结果
        :param api_key: API密钥
        :param base_url: API地址
        :param model: 语言模型
        :param provider: 语言模型提供商
        :param prompt: 提示词
        :param transcriptions_provider: 语音转文本提供商
        :param transcriptions_api_key: 语音转文本API密钥
        :param transcriptions_base_url: 语音转文本API地址
        """
        sc = SummaryConfig()
        api_key = api_key or sc.api_key
        base_url = base_url or sc.base_url
        model = model or sc.model
        provider = provider or sc.provider
        prompt = prompt or sc.prompt
        transcriptions_provider = transcriptions_provider or sc.transcriptions_provider
        transcriptions_api_key = transcriptions_api_key or sc.transcriptions_api_key
        transcriptions_base_url = transcriptions_base_url or sc.transcriptions_base_url

        if not api_key or not base_url:
            raise ValueError("AI总结未配置")
        if not transcriptions_api_key or not transcriptions_base_url:
            raise ValueError("语音转文本未配置")

        media = self.media if isinstance(self.media, list) else [self.media]
        subtitles = ""
        tasks = []
        for i in media:
            if isinstance(i, Video):
                subtitles = await self._video_to_subtitles(
                    i,
                    transcriptions_api_key,
                    transcriptions_base_url,
                    transcriptions_provider,
                )
                if not subtitles:
                    img = await asyncio.to_thread(video_to_png, i.path)
                    tasks.append(image_proces(img))
            elif isinstance(i, Image):
                tasks.append(image_proces(i.path))
            else:
                ...

        result: list[str] = [
            i for i in await asyncio.gather(*tasks, return_exceptions=True) if not isinstance(i, BaseException)
        ]
        content = [
            {
                "type": "text",
                "text": (f"标题: {self.pr.title}" if self.pr.title else "")
                + (f"\n正文: {self.pr.desc}" if self.pr.desc else "")
                + (f"\n视频字幕: {subtitles}" if subtitles else ""),
            }
        ]
        imgs = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{i}"},
            }
            for i in result
        ]

        template = [
            SystemMessage(prompt),
            HumanMessage(content=content + imgs),
            HumanMessage(content=[{"type": "text", "text": "请对以上内容进行总结！"}]),
        ]

        llm = LLM(
            provider,
            api_key,
            base_url,
            model,
        )
        model = llm.provider
        answer = await model.ainvoke(template)
        return SummaryResult(answer.content)

    @staticmethod
    async def _video_to_subtitles(
        media_: Video,
        api_key: str,
        base_url: str,
        transcriptions_provider: Literal["openai", "fast_whisper", "azure"],
    ) -> str:
        if not media_.subtitles:
            tr = await Transcriptions(api_key=api_key, base_url=base_url).transcription(
                media_.path, transcriptions_provider=transcriptions_provider
            )
            media_.subtitles = Subtitles([Subtitle(begin=str(c.begin), end=str(c.end), text=c.text) for c in tr.chucks])
        return media_.subtitles.to_str() if media_.subtitles.subtitles[5:] else ""

    def delete(self):
        """删除文件"""
        if self.save_dir:
            if self.save_dir.exists():
                return shutil.rmtree(self.save_dir)
            return None

        if isinstance(self.media, list):
            p = [i.path for i in self.media if i.exists()]
            if p:
                shutil.rmtree(os.path.dirname(p[0]))
        else:
            if self.media.exists():
                os.remove(self.media.path)
