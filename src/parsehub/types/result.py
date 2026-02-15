import shutil
import time
from abc import ABC
from collections.abc import Awaitable, Callable
from pathlib import Path

from bs4 import BeautifulSoup
from markdown import markdown as md_to_html

from ..config import DownloadConfig, GlobalConfig
from ..errors import DownloadError
from ..utils.downloader import download
from ..utils.util import progress
from .media_file import AniFile, AnyMediaFile, ImageFile, LivePhotoFile, VideoFile
from .media_ref import AniRef, AnyMediaRef, ImageRef, LivePhotoRef, VideoRef
from .platform import Platform


class ParseResult(ABC):  # noqa: B024
    """解析结果基类"""

    def __init__(
        self,
        title: str,
        media: list[AnyMediaRef] | AnyMediaRef,
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
        save_dir = Path(path) if path else GlobalConfig.default_save_dir
        media_list = self.media if isinstance(self.media, list) else [self.media]
        is_single = not isinstance(self.media, list)

        result_list: list[AnyMediaFile] = []
        output_dir = save_dir.joinpath(f"{time.time_ns()}")

        for i, media in enumerate(media_list):
            dl_progress = None
            dl_progress_args = ()
            if callback and is_single:

                async def _byte_callback(current, total, *args):
                    await callback(current, total, progress(current, total, "百分比"), *args)

                dl_progress = _byte_callback
                dl_progress_args = callback_args

            try:
                f = await download(
                    media.url,
                    f"{output_dir}/{i}.{media.ext}",
                    headers=config.headers,
                    proxies=config.proxy,
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

            # LivePhoto 额外下载视频部分
            if isinstance(media, LivePhotoRef) and media.video_url:
                try:
                    vf = await download(
                        media.video_url,
                        f"{output_dir}/{i}_video.{media.video_ext}",
                        headers=config.headers,
                        proxies=config.proxy,
                    )
                except Exception as e:
                    shutil.rmtree(output_dir, ignore_errors=True)
                    raise DownloadError(f"LivePhoto视频下载失败: {e}") from e
                mf.video_path = vf

            result_list.append(mf)

            if callback and not is_single:
                await callback(
                    len(result_list),
                    len(media_list),
                    progress(len(result_list), len(media_list), "数量"),
                    *callback_args,
                )

        result_media = result_list[0] if is_single else result_list
        return DownloadResult(result_media, output_dir)


class VideoParseResult(ParseResult):
    """单个视频"""

    def __init__(
        self,
        title: str = "",
        video: str | VideoRef = None,
        content: str = "",
        raw_url: str = None,
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

    def __init__(
        self,
        title: str = "",
        photo: list[str | ImageRef | LivePhotoRef] = None,
        content: str = "",
        raw_url: str = None,
    ):
        photo = [ImageRef(url=p) if isinstance(p, str) else p for p in photo]
        super().__init__(title=title, media=photo, content=content, raw_url=raw_url)


class MultimediaParseResult(ParseResult):
    """多视频 / 视频 + 图片 / GIF / 实况照片"""

    def __init__(
        self,
        title: str = "",
        media: list[AnyMediaRef] = None,
        content: str = "",
        raw_url: str = None,
    ):
        super().__init__(title=title, media=media, content=content, raw_url=raw_url)


class RichTextParseResult(ParseResult):
    """图文混排的文章"""

    def __init__(
        self,
        title: str = "",
        media: list[AnyMediaRef] = None,
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
    def __init__(self, media: AnyMediaFile | list[AnyMediaFile], output_dir: str | Path):
        """
        下载结果
        :param media: 本地媒体路径
        :param output_dir: 输出目录
        """
        self.media = media
        self.output_dir = Path(output_dir).resolve()


AnyParseResult = VideoParseResult | ImageParseResult | MultimediaParseResult | RichTextParseResult
