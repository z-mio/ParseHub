from ...provider_api.toutiao import Toutiao, ToutiaoArticle, ToutiaoError, ToutiaoVideoPost
from ...types import (
    AnyMediaRef,
    ImageParseResult,
    ImageRef,
    ParseError,
    Platform,
    RichTextParseResult,
    VideoParseResult,
    VideoRef,
)
from ..base.base import BaseParser


class ToutiaoParser(BaseParser):
    __platform__ = Platform.TOUTIAO
    __supported_type__ = ["文章", "视频", "微头条"]
    __match__ = (
        r"^(http(s)?://)?(www|m)\.toutiao\.com/"
        r"(article/\d+|video/\d+|w/\d+|group/\d+|item/\d+|a\d+|i\d+|is/\w+)"
    )
    __redirect_keywords__ = ["toutiao.com/is/"]

    async def _do_parse(self, raw_url: str) -> ImageParseResult | RichTextParseResult | VideoParseResult:
        try:
            post = await Toutiao(proxy=self.proxy).parse(raw_url)
        except ToutiaoError as e:
            raise ParseError(f"今日头条解析失败: {e}") from e

        if isinstance(post, ToutiaoVideoPost):
            video = post.video
            return VideoParseResult(
                title=post.title,
                video=VideoRef(
                    url=video.url,
                    thumb_url=video.thumb_url,
                    duration=video.duration,
                    width=video.width,
                    height=video.height,
                ),
            )
        if isinstance(post, ToutiaoArticle):
            media: list[AnyMediaRef] = [
                ImageRef(url=image.url, width=image.width, height=image.height) for image in post.images
            ]
            media.extend(
                VideoRef(
                    url=video.url,
                    thumb_url=video.thumb_url,
                    duration=video.duration,
                    width=video.width,
                    height=video.height,
                )
                for video in post.videos
            )
            return RichTextParseResult(
                title=post.title,
                media=media,
                markdown_content=post.markdown_content,
            )

        return ImageParseResult(
            title="",
            content=post.content,
            photo=[ImageRef(url=image.url, width=image.width, height=image.height) for image in post.images] or None,
        )


__all__ = ["ToutiaoParser"]
