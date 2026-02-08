from ...parsers.base import BaseParser
from ...provider_api.xiaoheihe import XiaoHeiHeAPI, XiaoHeiHeMediaType, XiaoHeiHePost, XiaoHeiHePostType
from ...types import (
    Ani,
    AnyParseResult,
    Image,
    ImageParseResult,
    MultimediaParseResult,
    RichTextParseResult,
    Video,
    VideoParseResult,
)
from ...types.platform import Platform


class XiaoHeiHeParser(BaseParser):
    __platform__ = Platform.XIAOHEIHE
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+xiaoheihe.cn/(v3|app)/bbs/(app|link).+"
    __redirect_keywords__ = ["api.xiaoheihe"]

    async def parse(self, url: str) -> AnyParseResult:
        url = await self.get_raw_url(url)
        xhh: XiaoHeiHePost = await XiaoHeiHeAPI(proxy=self.cfg.proxy).parse(url)
        media = self.__parse_media(xhh)
        v = {"title": xhh.title, "content": xhh.content, "raw_url": url}
        match xhh.type:
            case XiaoHeiHePostType.VIDEO:
                return VideoParseResult(video=media, **v)
            case XiaoHeiHePostType.IMAGE:
                if not media or all(isinstance(m, Image) for m in media):
                    return ImageParseResult(photo=media, **v)
                return MultimediaParseResult(media=media, **v)
            case XiaoHeiHePostType.ARTICLE:
                return RichTextParseResult(title=xhh.title, media=media, markdown_content=xhh.content, raw_url=url)

    @staticmethod
    def __parse_media(xhh: XiaoHeiHePost):
        match xhh.type:
            case XiaoHeiHePostType.VIDEO:
                return Video(path=xhh.media[0].url, thumb_url=xhh.media[0].thumb_url)
            case XiaoHeiHePostType.IMAGE | XiaoHeiHePostType.ARTICLE:
                images: list[Image | Ani] = []
                for i in xhh.media:
                    if i.type == XiaoHeiHeMediaType.IMAGE:
                        images.append(Image(i.url, width=i.width, height=i.height))
                    else:
                        images.append(Ani(i.url, width=i.width, height=i.height))

                return images
