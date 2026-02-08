import asyncio
import os
import shutil
import time
from abc import ABC
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from markdown import markdown as md_to_html

from ..config import SummaryConfig
from ..config.config import DownloadConfig
from ..tools import LLM, Transcriptions
from ..utiles.download_file import download_file
from ..utiles.utile import image_proces, progress, video_to_png
from .error import DownloadError
from .media import AnyMedia, Image, LivePhoto, Video
from .platform import Platform
from .subtitles import Subtitle, Subtitles
from .summary import SummaryResult


class ParseResult(ABC):  # noqa: B024
    """解析结果基类"""

    def __init__(
        self,
        title: str,
        media: list[AnyMedia] | AnyMedia,
        content: str = "",
        raw_url: str = None,
        platform: Platform = None,
    ):
        """
        :param title: 标题
        :param media: 媒体下载链接
        :param content: 正文
        :param raw_url: 原始帖子链接
        :param platform: 平台
        """
        self.title = (title or "").strip()
        self.media = media
        self.content = (content or "").strip()
        self.raw_url = raw_url
        self.platform = platform

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(platform={self.platform}, title={self.title or "''"},"
            f" content={self.content or "''"}, raw_url={self.raw_url})"
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
        media_list = self.media if isinstance(self.media, list) else [self.media]
        is_single = not isinstance(self.media, list)

        result_list = []
        op = save_dir.joinpath(f"{time.time_ns()}")

        for i, media in enumerate(media_list):
            if media.exists():
                result_list.append(media)
                continue

            dl_progress = None
            dl_progress_args = ()
            if callback and is_single:

                async def _byte_callback(current, total, *args):
                    await callback(current, total, progress(current, total, "百分比"), *args)

                dl_progress = _byte_callback
                dl_progress_args = callback_args

            try:
                f = await download_file(
                    media.path,
                    f"{op}/{i}.{media.ext}",
                    proxies=config.proxy,
                    headers=config.headers,
                    progress=dl_progress,
                    progress_args=dl_progress_args,
                )
            except Exception as e:
                shutil.rmtree(op, ignore_errors=True)
                raise DownloadError(f"下载失败: {e}") from e

            n_m = media.__class__(**vars(media))
            n_m.path = f

            # LivePhoto 额外下载视频部分
            if isinstance(media, LivePhoto) and media.video_path:
                try:
                    vf = await download_file(
                        media.video_path,
                        f"{op}/{i}_video.{media.video_ext}",
                        proxies=config.proxy,
                        headers=config.headers,
                    )
                except Exception as e:
                    shutil.rmtree(op, ignore_errors=True)
                    raise DownloadError(f"LivePhoto视频下载失败: {e}") from e
                n_m.video_path = vf

            result_list.append(n_m)

            if callback and not is_single:
                await callback(
                    len(result_list),
                    len(media_list),
                    progress(len(result_list), len(media_list), "数量"),
                    *callback_args,
                )

        result_media = result_list[0] if is_single else result_list
        return DownloadResult(self, result_media, op)

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
    """单个视频"""

    def __init__(
        self,
        title: str = "",
        video: str | Video = None,
        content: str = "",
        raw_url: str = None,
    ):
        video = Video(video) if isinstance(video, str) else video
        super().__init__(
            title=title,
            media=video,
            content=content,
            raw_url=raw_url,
        )


class ImageParseResult(ParseResult):
    """单图 / 多图 / 图集 / 实况照片"""

    def __init__(
        self,
        title: str = "",
        photo: list[str | Image | LivePhoto] = None,
        content: str = "",
        raw_url: str = None,
    ):
        photo = [Image(p, thumb_url=p) if isinstance(p, str) else p for p in photo]
        super().__init__(title=title, media=photo, content=content, raw_url=raw_url)


class MultimediaParseResult(ParseResult):
    """多视频 / 视频 + 图片 / GIF / 实况照片"""

    def __init__(
        self,
        title: str = "",
        media: list[AnyMedia] = None,
        content: str = "",
        raw_url: str = None,
    ):
        super().__init__(title=title, media=media, content=content, raw_url=raw_url)


class RichTextParseResult(ParseResult):
    """图文混排的文章"""

    def __init__(
        self,
        title: str = "",
        media: list[AnyMedia] = None,
        markdown_content: str = "",
        raw_url: str = None,
    ):
        """

        :param title: 标题
        :param media: 文章中的媒体
        :param markdown_content: markdown 格式正文
        :param raw_url: 原始 URL
        """
        self.markdown_content = markdown_content
        super().__init__(title=title, media=media, content=self.plaintext_content, raw_url=raw_url)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(title={self.title or "''"},"
            f" markdown_content={self.markdown_content or "''"}, raw_url={self.raw_url})"
        )

    @property
    def plaintext_content(self) -> str:
        """从 markdown 转换为纯文本"""
        return "".join(BeautifulSoup(md_to_html(self.markdown_content), "lxml").find_all(string=True)).strip()


class DownloadResult:
    def __init__(self, parse_result: ParseResult, media: AnyMedia | list[AnyMedia], save_dir: str | Path = None):
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
                + (f"\n正文: {self.pr.content}" if self.pr.content else "")
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


AnyParseResult = VideoParseResult | ImageParseResult | MultimediaParseResult | RichTextParseResult
