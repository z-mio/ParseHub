import json
import shutil
import time
from abc import ABC
from dataclasses import asdict
from pathlib import Path
from typing import ClassVar

import aiofiles
from bs4 import BeautifulSoup
from markdown import markdown as md_to_html
from slugify import slugify

from ..config import GlobalConfig
from ..errors import DeleteError, DownloadError
from ..utils.downloader import download
from ..utils.utils import get_event_loop
from .callback import ProgressCallback
from .media_file import AniFile, AnyMediaFile, ImageFile, LivePhotoFile, VideoFile
from .media_ref import AniRef, AnyMediaRef, ImageRef, LivePhotoRef, VideoRef
from .platform import Platform
from .post import PostType


class ParseResult(ABC):  # noqa: B024
    """解析结果基类"""

    type: ClassVar[PostType] = PostType.UNKNOWN

    def __init__(
        self,
        raw_url: str,
        title: str = "",
        content: str = "",
        media: list[AnyMediaRef] | AnyMediaRef | None = None,
        platform: Platform | None = None,
    ):
        """
        :param title: 标题
        :param media: 媒体下载链接
        :param content: 正文 (纯文本)
        :param raw_url: 原始帖子链接
        :param platform: 平台
        """
        self.title = (title or "").strip()
        self.content = (content or "").strip()
        self.media = media
        self.raw_url = raw_url
        self.platform = platform

    def __repr__(self):
        media_count = f"[{len(self.media if isinstance(self.media, list) else [self.media])}]" if self.media else None
        return (
            f"{self.__class__.__name__}(platform={self.platform}, title={self.title or ''},"
            f" content={self.content or ''}, media={media_count}, "
            f"raw_url={self.raw_url})"
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        media = None
        if isinstance(self.media, list):
            media = [asdict(m) for m in self.media]
        elif self.media:
            media = asdict(self.media)

        return {
            "platform": self.platform.id if self.platform else None,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "raw_url": self.raw_url,
            "media": media,
        }

    async def _do_download(
        self,
        *,
        output_dir: str | Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        proxy: str | None = None,
        headers: dict | None = None,
    ) -> "DownloadResult":
        """
        执行下载
        :param output_dir: 输出的子目录
        :param callback: 下载进度回调函数
        :param callback_args: 回调函数的参数
        :param proxy: 代理
        :param headers: 请求头
        :return: DownloadResult
        """
        media_list = self.media if isinstance(self.media, list) else [self.media]
        is_single = not isinstance(self.media, list)

        result_list: list[AnyMediaFile] = []

        for i, media in enumerate(media_list):
            dl_progress = None
            dl_progress_args = ()
            if callback and is_single:

                async def _byte_callback(current, total, *args):
                    await callback(current, total, "bytes", *args)

                dl_progress = _byte_callback
                dl_progress_args = callback_args

            try:
                f = await download(
                    media.url,
                    f"{output_dir}/{i}.{media.ext}",
                    headers=headers,
                    proxies=proxy,
                    progress=dl_progress,
                    progress_args=dl_progress_args,
                )
            except Exception as e:
                shutil.rmtree(output_dir, ignore_errors=True)
                raise DownloadError(f"下载失败: {e}") from e

            match media:
                case ImageRef():
                    mf = ImageFile(path=f, width=media.width, height=media.height)
                case VideoRef():
                    mf = VideoFile(path=f, width=media.width, height=media.height, duration=media.duration)
                case AniRef():
                    mf = AniFile(path=f, width=media.width, height=media.height, duration=media.duration)
                case LivePhotoRef():
                    mf = LivePhotoFile(path=f, width=media.width, height=media.height, duration=media.duration)
                    if media.video_url:
                        try:
                            vf = await download(
                                media.video_url,
                                f"{output_dir}/{i}_video.{media.video_ext}",
                                headers=headers,
                                proxies=proxy,
                            )
                        except Exception as e:
                            shutil.rmtree(output_dir, ignore_errors=True)
                            raise DownloadError(f"LivePhoto 视频下载失败: {e}") from e
                        else:
                            mf.video_path = vf

            result_list.append(mf)

            if callback and not is_single:
                await callback(
                    len(result_list),
                    len(media_list),
                    "count",
                    *callback_args,
                )

        result_media = result_list[0] if is_single else result_list
        return DownloadResult(result_media, output_dir)

    async def download(
        self,
        path: str | Path | None = None,
        *,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        proxy: str | None = None,
        save_metadata: bool = False,
    ) -> "DownloadResult":
        """
        :param path: 保存路径
        :param callback: 下载进度回调函数
        :param callback_args: 下载进度回调函数参数
        :param proxy: 代理
        :param save_metadata: 保存解析结果为 metadata.json, 默认为 False
        :return: DownloadResult

        Note:
            下载进度回调函数签名::

                async def callback(current: int, total: int, unit: Literal['bytes', 'count'], *args) -> None

            - current: 当前进度值
            - total: 总进度值
            - unit: 进度单位
                - ``bytes``: 字节进度，用于单文件下载时报告已下载/总字节数
                - ``count``: 计数进度，用于多文件下载时报告已完成/总文件数
        """
        save_dir = Path(path) if path else GlobalConfig.default_save_dir
        r = slugify(
            self.title or self.content or str(time.time_ns()), allow_unicode=True, max_length=20, lowercase=False
        )
        output_dir = save_dir.joinpath(r)
        counter = 2
        while output_dir.exists():
            output_dir = save_dir.joinpath(f"{r}_{counter}")
            counter += 1
        output_dir.mkdir(parents=True, exist_ok=True)

        if save_metadata:
            async with aiofiles.open(output_dir.joinpath("metadata.json"), "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.to_dict(), ensure_ascii=False, indent=4))

        try:
            return await self._do_download(
                output_dir=output_dir, callback=callback, callback_args=callback_args, proxy=proxy
            )
        except Exception as e:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise e

    def download_sync(
        self,
        path: str | Path | None = None,
        *,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        proxy: str | None = None,
        save_metadata: bool = False,
    ) -> "DownloadResult":
        """
        :param path: 保存路径
        :param callback: 下载进度回调函数
        :param callback_args: 下载进度回调函数参数
        :param proxy: 代理
        :param save_metadata: 保存解析结果为 metadata.json, 默认为 False
        :return: DownloadResult

        Note:
            下载进度回调函数签名::

                async def callback(current: int, total: int, unit: Literal['bytes', 'count'], *args) -> None

            - current: 当前进度值
            - total: 总进度值
            - unit: 进度单位
                - ``bytes``: 字节进度，用于单文件下载时报告已下载/总字节数
                - ``count``: 计数进度，用于多文件下载时报告已完成/总文件数
        """
        return get_event_loop().run_until_complete(
            self.download(
                path, callback=callback, callback_args=callback_args, proxy=proxy, save_metadata=save_metadata
            )
        )


class VideoParseResult(ParseResult):
    """单个视频"""

    type = PostType.VIDEO

    def __init__(
        self,
        raw_url: str,
        title: str = "",
        video: str | VideoRef | None = None,
        content: str = "",
    ):
        video = VideoRef(url=video) if isinstance(video, str) else video
        super().__init__(
            title=title,
            media=video,
            content=content,
            raw_url=raw_url,
        )


class ImageParseResult(ParseResult):
    """单图 / 多图 / 图集 / 实况照片"""

    type = PostType.IMAGE

    def __init__(
        self,
        raw_url: str,
        title: str = "",
        photo: list[str | ImageRef | LivePhotoRef] | None = None,
        content: str = "",
    ):
        if photo:
            photo = [ImageRef(url=p) if isinstance(p, str) else p for p in photo]
        super().__init__(title=title, media=photo, content=content, raw_url=raw_url)


class MultimediaParseResult(ParseResult):
    """多视频 / 视频 + 图片 / GIF / 实况照片"""

    type = PostType.MULTIMEDIA

    def __init__(
        self,
        raw_url: str,
        title: str = "",
        media: list[AnyMediaRef] | None = None,
        content: str = "",
    ):
        super().__init__(title=title, media=media, content=content, raw_url=raw_url)


class RichTextParseResult(ParseResult):
    """图文混排的文章"""

    type = PostType.RICHTEXT

    def __init__(
        self,
        raw_url: str,
        title: str = "",
        media: list[AnyMediaRef] | None = None,
        markdown_content: str = "",
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
        media_count = f"[{len(self.media if isinstance(self.media, list) else [self.media])}]" if self.media else None
        return (
            f"{self.__class__.__name__}(title={self.title or ''},"
            f" markdown_content={self.markdown_content or ''}, media={media_count} raw_url={self.raw_url})"
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        data = super().to_dict()
        # 在 "content" 后面插入 "markdown_content"
        result = {}
        for key, value in data.items():
            result[key] = value
            if key == "content":
                result["markdown_content"] = self.markdown_content
        return result

    @property
    def plaintext_content(self) -> str:
        """从 markdown 转换为纯文本"""
        return "".join(BeautifulSoup(md_to_html(self.markdown_content), "lxml").find_all(string=True)).strip()


class DownloadResult:
    def __init__(self, media: AnyMediaFile | list[AnyMediaFile], output_dir: str | Path):
        """
        下载结果
        :param media: 本地媒体路径
        :param output_dir: 输出目录
        """
        self.media = media
        self.output_dir = Path(output_dir).resolve()

    def delete(self):
        try:
            shutil.rmtree(self.output_dir)
        except Exception as e:
            raise DeleteError(f"目录删除失败: {self.output_dir}") from e

    def __repr__(self):
        return f"{self.__class__.__name__}(media={self.media}, output_dir={self.output_dir})"


AnyParseResult = VideoParseResult | ImageParseResult | MultimediaParseResult | RichTextParseResult
