from ...provider_api.zhihu import ZhihuAPI, ZhihuPin, ZhihuPinType, ZhihuQA, ZhihuZhuanLan
from ...types import (
    ImageParseResult,
    ImageRef,
    MultimediaParseResult,
    Platform,
    RichTextParseResult,
    VideoParseResult,
    VideoRef,
)
from ..base.base import BaseParser


class ZhihuParser(BaseParser):
    __platform__ = Platform.ZHIHU
    __supported_type__ = ["问答", "专栏", "圈子"]
    __match__ = r"^(http(s)?://)?(www|zhuanlan).zhihu.com/(pin|question|p)/.*"

    async def _do_parse(
        self, raw_url: str
    ) -> RichTextParseResult | MultimediaParseResult | ImageParseResult | VideoParseResult:
        if not (c := self.cookie.get_value()):
            raise ValueError("知乎需要配置已登录的 Cookie")
        result = await ZhihuAPI(cookie=c, proxy=self.proxy).parse(raw_url)
        match result:
            case ZhihuQA():
                if not result.markdown_answer:
                    return MultimediaParseResult(title=result.question)
                return RichTextParseResult(
                    title=result.question,
                    media=[ImageRef(url=i) for i in result.imgs],
                    markdown_content=result.markdown_answer,
                )
            case ZhihuZhuanLan():
                return RichTextParseResult(
                    title=result.title,
                    markdown_content=result.markdown_content,
                    media=[ImageRef(url=i) for i in result.imgs],
                )
            case ZhihuPin():
                match result.type:
                    case ZhihuPinType.TEXT:
                        return ImageParseResult(title=result.title, content=result.plaintext_content)
                    case ZhihuPinType.IMAGE:
                        return ImageParseResult(
                            title=result.title,
                            content=result.plaintext_content,
                            photo=[
                                ImageRef(url=i.url, thumb_url=i.thumb_url, width=i.width, height=i.height)
                                for i in result.media
                            ],
                        )
                    case ZhihuPinType.VIDEO:
                        v = result.media[0]
                        return VideoParseResult(
                            title=result.title,
                            content=result.plaintext_content,
                            video=VideoRef(
                                url=v.url, thumb_url=v.thumb_url, height=v.height, width=v.width, duration=v.duration
                            ),
                        )


__all__ = ["ZhihuParser"]
