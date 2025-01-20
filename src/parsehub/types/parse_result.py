import os
import shutil
import time
from pathlib import Path
from typing import Callable, Generic, TypeVar, Literal
from .media import Media, Video
from ..utiles.utile import progress, img2base64
from ..utiles.download_file import download_file
import asyncio
from abc import ABC
from langchain_core.messages import HumanMessage, SystemMessage
from ..tools import LLM, Transcriptions
from .media import Image, MediaT
from .subtitles import Subtitles, Subtitle
from .summary_result import SummaryResult
from ..config.config import DownloadConfig, SummaryConfig
from ..utiles.utile import video_to_png


T = TypeVar("T", bound="ParseResult")


class ParseResult(ABC):
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
        return f"{self.__class__.__name__}(title={self.title or "''"}, desc={self.desc or "''"}, raw_url={self.raw_url})"

    async def download(
        self,
        path: str | Path = None,
        callback: Callable = None,
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
        if isinstance(self.media, list):
            path_list = []
            op = (Path(path) if path else config.save_dir).joinpath(f"{time.time_ns()}")
            for i, image in enumerate(self.media):
                if not image.is_url:
                    path_list.append(image)
                    continue

                f = await download_file(
                    image.path,
                    f"{op}/{i}.{image.ext}",
                    proxies=config.proxy,
                    headers=config.headers,
                )

                path_list.append(image.__class__(f, ext=image.ext))

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

            r = await download_file(
                self.media.path,
                config.save_dir / f"{time.time_ns()}.{self.media.ext}",
                headers=config.headers,
                proxies=config.proxy,
                progress=_callback if callback else None,
                progress_args=callback_args,
            )

            # 小于10KB为下载失败
            if not os.stat(r).st_size > 10 * 1024:
                os.remove(r)
                raise Exception("下载失败")
            return DownloadResult(self, self.media.__class__(r, ext=self.media.ext))

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
        sr = await dr.summary(
            api_key, base_url, model, provider, prompt, transcriptions_provider
        )
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


class DownloadResult(Generic[T]):
    def __init__(
        self, parse_result: T, media: list[MediaT] | MediaT, save_dir: str | Path = None
    ):
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
        transcriptions_provider: str = None,
    ) -> "SummaryResult":
        """总结解析结果
        :param api_key: API密钥
        :param base_url: API地址
        :param model: 语言模型
        :param provider: 语言模型提供商
        :param prompt: 提示词
        :param transcriptions_provider: 语音转文本提供商
        """
        sc = SummaryConfig()
        api_key = api_key or sc.api_key
        base_url = base_url or sc.base_url
        model = model or sc.model
        provider = provider or sc.provider
        prompt = prompt or sc.prompt
        transcriptions_provider = transcriptions_provider or sc.transcriptions_provider

        if not api_key or not base_url:
            raise ValueError("AI总结未配置")

        media = self.media if isinstance(self.media, list) else [self.media]
        subtitles = ""
        tasks = []
        for i in media:
            if isinstance(i, Video):
                subtitles = await self._video_to_subtitles(
                    i, api_key, base_url, transcriptions_provider
                )
                if not subtitles:
                    img = await asyncio.to_thread(video_to_png, i.path)
                    tasks.append(img2base64(img))
            elif isinstance(i, Image):
                tasks.append(img2base64(i.path))
            else:
                ...

        result: list[str] = [
            i
            for i in await asyncio.gather(*tasks, return_exceptions=True)
            if not isinstance(i, BaseException)
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
        media_: Media,
        api_key: str,
        base_url: str,
        transcriptions_provider: str,
    ) -> str:
        if not media_.subtitles:
            tr = await Transcriptions(api_key=api_key, base_url=base_url).transcription(
                media_.path, transcriptions_provider=transcriptions_provider
            )
            media_.subtitles = Subtitles(
                [
                    Subtitle(begin=str(c.begin), end=str(c.end), text=c.text)
                    for c in tr.chucks
                ]
            )
        return media_.subtitles.to_str() if media_.subtitles.subtitles[5:] else ""

    def delete(self):
        """删除文件"""
        if self.save_dir:
            return shutil.rmtree(self.save_dir)

        if isinstance(self.media, list):
            p = [i.path for i in self.media if i.exists()]
            if p:
                shutil.rmtree(os.path.dirname(p[0]))
        else:
            if self.media.exists():
                os.remove(self.media.path)
