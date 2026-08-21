from pathlib import Path

from ...provider_api.douban import IMAGE_REFERER, Douban, DoubanError, DoubanPhoto, DoubanVideo
from ...types import (
    AniRef,
    AnyMediaRef,
    DownloadResult,
    ImageRef,
    ParseError,
    Platform,
    ProgressCallback,
    RichTextParseResult,
    VideoRef,
)
from ...utils.helpers import UA
from ..base.base import BaseParser


class DoubanParser(BaseParser):
    __platform__ = Platform.DOUBAN
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?(((www|m)\.)?douban\.com/((group/)?topic/\d+|doubanapp/dispatch)|douc\.cc/.+)"
    __redirect_keywords__ = ["douc.cc", "doubanapp/dispatch"]

    async def _do_parse(self, raw_url: str) -> "DoubanRichTextParseResult":
        try:
            topic = await Douban(proxy=self.proxy, cookie=self.cookie.get_value()).parse(raw_url)
        except DoubanError as e:
            raise ParseError(f"豆瓣解析失败: {e.msg}") from e
        except Exception as e:
            raise ParseError("豆瓣解析失败: 未知错误") from e

        # 图片和视频在正文里有位置关系, 交给 RichText 由 markdown 保留顺序
        media: list[AnyMediaRef] = [
            *([self.to_video_ref(topic.video)] if topic.video else []),
            *(self.to_media_ref(p) for p in topic.photos),
        ]
        return DoubanRichTextParseResult(title=topic.title, media=media, markdown_content=topic.markdown_content)

    @staticmethod
    def to_video_ref(video: DoubanVideo) -> VideoRef:
        return VideoRef(
            url=video.url,
            thumb_url=video.thumb_url,
            width=video.width,
            height=video.height,
            duration=video.duration,
        )

    @staticmethod
    def to_media_ref(photo: DoubanPhoto) -> ImageRef | AniRef:
        ref_type = AniRef if photo.is_animated else ImageRef
        return ref_type(
            url=photo.url,
            ext=photo.ext,
            thumb_url=photo.thumb_url,
            width=photo.width,
            height=photo.height,
        )


class DoubanRichTextParseResult(RichTextParseResult):
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
        headers = {"User-Agent": UA, "Referer": IMAGE_REFERER}
        return await super()._do_download(
            output_dir=output_dir,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            headers=headers,
            connections=connections,
        )


__all__ = ["DoubanParser", "DoubanRichTextParseResult"]
