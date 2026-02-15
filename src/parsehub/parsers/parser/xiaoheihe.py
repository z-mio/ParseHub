from ...parsers.base import BaseParser
from ...provider_api.xiaoheihe import XiaoHeiHeAPI, XiaoHeiHeMediaType, XiaoHeiHePost, XiaoHeiHePostType
from ...types import (
    AniRef,
    AnyParseResult,
    ImageParseResult,
    ImageRef,
    MultimediaParseResult,
    RichTextParseResult,
    VideoParseResult,
    VideoRef,
)
from ...types.platform import Platform


class XiaoHeiHeParser(BaseParser):
    __platform__ = Platform.XIAOHEIHE
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+xiaoheihe.cn/(v3|app)/bbs/(app|link).+"
    __redirect_keywords__ = ["api.xiaoheihe"]

    async def parse(self, url: str) -> AnyParseResult:
        xhh: XiaoHeiHePost = await XiaoHeiHeAPI(proxy=self.cfg.proxy).parse(url)
        media = self.__parse_media(xhh)
        v = {"title": xhh.title, "content": xhh.content, "raw_url": url}
        match xhh.type:
            case XiaoHeiHePostType.VIDEO:
                return VideoParseResult(video=media, **v)
            case XiaoHeiHePostType.IMAGE:
                if not media or all(isinstance(m, ImageRef) for m in media):
                    return ImageParseResult(photo=media, **v)
                return MultimediaParseResult(media=media, **v)
            case XiaoHeiHePostType.ARTICLE:
                return RichTextParseResult(title=xhh.title, media=media, markdown_content=xhh.content, raw_url=url)

    @staticmethod
    def __parse_media(xhh: XiaoHeiHePost):
        match xhh.type:
            case XiaoHeiHePostType.VIDEO:
                return VideoRef(url=xhh.media[0].url, thumb_url=xhh.media[0].thumb_url)
            case XiaoHeiHePostType.IMAGE | XiaoHeiHePostType.ARTICLE:
                images: list[ImageRef | AniRef] = []
                for i in xhh.media:
                    if i.type == XiaoHeiHeMediaType.IMAGE:
                        images.append(ImageRef(url=i.url, width=i.width, height=i.height))
                    else:
                        images.append(AniRef(url=i.url, width=i.width, height=i.height))

                return images
