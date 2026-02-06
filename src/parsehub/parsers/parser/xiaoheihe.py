from typing import Union

from ...parsers.base import BaseParser
from ...provider_api.xiaoheihe import XiaoHeiHeAPI, XiaoHeiHeMediaType, XiaoHeiHePost, XiaoHeiHePostType
from ...types import Ani, Image, ImageParseResult, Media, MultimediaParseResult, Video, VideoParseResult


class XiaoHeiHeParser(BaseParser):
    __platform_id__ = "xiaoheihe"
    __platform__ = "小黑盒"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+xiaoheihe.cn/(v3|app)/bbs/(app|link).+"
    __redirect_keywords__ = ["api.xiaoheihe"]

    async def parse(
        self, url: str
    ) -> Union["XiaoHeiHeImageParseResult", "XiaoHeiHeVideoParseResult", "XiaoHeiHeMultimediaParseResult"]:
        url = await self.get_raw_url(url)
        xhh: XiaoHeiHePost = await XiaoHeiHeAPI(proxy=self.cfg.proxy).parse(url)
        match xhh.type:
            case XiaoHeiHePostType.VIDEO:
                return XiaoHeiHeVideoParseResult(
                    title=xhh.title,
                    video=Video(path=xhh.media[0].url, thumb_url=xhh.media[0].thumb_url),
                    raw_url=url,
                    desc=xhh.text_content,
                )
            case XiaoHeiHePostType.IMAGE | XiaoHeiHePostType.ARTICLE:
                images = []
                for i in xhh.media:
                    if i.type == XiaoHeiHeMediaType.IMAGE:
                        images.append(Image(i.url, width=i.width, height=i.height))
                    else:
                        images.append(Ani(i.url, width=i.width, height=i.height))

                if all(isinstance(m, Image) for m in images):
                    return XiaoHeiHeImageParseResult(
                        title=xhh.title, photo=images, desc=xhh.text_content, raw_url=url, xhh=xhh
                    )

                return XiaoHeiHeMultimediaParseResult(
                    title=xhh.title, media=images, desc=xhh.text_content, raw_url=url, xhh=xhh
                )


class XiaoHeiHeImageParseResult(ImageParseResult):
    def __init__(self, title: str, photo: list[str | Image], desc: str, raw_url: str, xhh: "XiaoHeiHePost"):
        super().__init__(title, photo, desc, raw_url)
        self.xhh = xhh


class XiaoHeiHeVideoParseResult(VideoParseResult):
    def __init__(self, title: str, video: str | Video, raw_url: str, desc: str = ""):
        super().__init__(title, video, raw_url, desc)


class XiaoHeiHeMultimediaParseResult(MultimediaParseResult):
    def __init__(self, title: str, media: list[Media], desc: str, raw_url: str, xhh: "XiaoHeiHePost"):
        super().__init__(title, media, desc, raw_url)
        self.xhh = xhh
