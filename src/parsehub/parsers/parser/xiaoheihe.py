from ...parsers.base import BaseParser
from ...provider_api.xiaoheihe import XiaoHeiHeAPI, XiaoHeiHeMediaType, XiaoHeiHePost, XiaoHeiHePostType
from ...types import (
    AniRef,
    AnyParseResult,
    ImageParseResult,
    ImageRef,
    MultimediaParseResult,
    ParseError,
    Platform,
    RichTextParseResult,
    VideoParseResult,
    VideoRef,
)


class XiaoHeiHeParser(BaseParser):
    __platform__ = Platform.XIAOHEIHE
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+xiaoheihe.cn/(v3|app)/bbs/(app|link).+"
    __redirect_keywords__ = ["api.xiaoheihe"]

    async def _do_parse(self, raw_url: str) -> AnyParseResult:
        xhh = await XiaoHeiHeAPI(proxy=self.proxy).parse(raw_url)
        match xhh.type:
            case XiaoHeiHePostType.VIDEO:
                return VideoParseResult(
                    video=self.__parse_video(xhh),
                    title=xhh.title,
                    content=xhh.content,
                )
            case XiaoHeiHePostType.IMAGE:
                media = self.__parse_images(xhh)
                if not media or all(isinstance(m, ImageRef) for m in media):
                    return ImageParseResult(photo=media, title=xhh.title, content=xhh.content)
                return MultimediaParseResult(media=media, title=xhh.title, content=xhh.content)
            case XiaoHeiHePostType.ARTICLE:
                return RichTextParseResult(
                    title=xhh.title,
                    media=self.__parse_images(xhh),
                    markdown_content=xhh.content,
                )
        raise ParseError("不支持的类型")

    @staticmethod
    def __parse_video(xhh: XiaoHeiHePost) -> VideoRef:
        if not xhh.media:
            raise ParseError("未获取到视频")
        media = xhh.media[0]
        return VideoRef(url=media.url, thumb_url=media.thumb_url)

    @staticmethod
    def __parse_images(xhh: XiaoHeiHePost) -> list[ImageRef | AniRef]:
        images: list[ImageRef | AniRef] = []
        for media in xhh.media or []:
            if media.type == XiaoHeiHeMediaType.IMAGE:
                images.append(ImageRef(url=media.url, width=media.width or 0, height=media.height or 0))
            else:
                images.append(AniRef(url=media.url, width=media.width or 0, height=media.height or 0))
        return images
