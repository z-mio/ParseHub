from ...provider_api.bangumi import Bangumi, BangumiError
from ...types import ImageRef, ParseError, Platform, RichTextParseResult
from ..base.base import BaseParser


class BangumiParser(BaseParser):
    __platform__ = Platform.BANGUMI
    __supported_type__ = ["条目讨论", "日志", "小组话题"]
    __match__ = (
        r"^(http(s)?://)?(www\.)?(bgm\.tv|bangumi\.tv|chii\.in)/"
        r"(subject/topic|group/topic|rakuen/topic/(subject|group)|blog)/\d+"
    )

    async def _do_parse(self, raw_url: str) -> RichTextParseResult:
        try:
            post = await Bangumi(proxy=self.proxy).parse(raw_url)
        except BangumiError as e:
            raise ParseError(f"Bangumi 解析失败: {e.msg}") from e

        return RichTextParseResult(
            title=post.title,
            media=[ImageRef(url=url) for url in post.images],
            markdown_content=post.markdown_content,
        )


__all__ = ["BangumiParser"]
