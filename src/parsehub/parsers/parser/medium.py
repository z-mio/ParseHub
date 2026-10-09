from ...provider_api.medium import Medium, MediumError
from ...types import ImageRef, ParseError, Platform, RichTextParseResult
from ..base.base import BaseParser


class MediumParser(BaseParser):
    __platform__ = Platform.MEDIUM
    __supported_type__ = ["文章"]
    __match__ = r"^(http(s)?://)?([\w-]+\.)?medium\.com/(.+/)?([^/?#]*-)?[0-9a-f]{8,12}(/|\?|#|$)"

    async def _do_parse(self, raw_url: str) -> RichTextParseResult:
        try:
            post = await Medium(proxy=self.proxy).parse(raw_url)
        except MediumError as e:
            raise ParseError(f"Medium 解析失败: {e}") from e

        return RichTextParseResult(
            title=post.title,
            media=[ImageRef(url=image.url, width=image.width, height=image.height) for image in post.images],
            markdown_content=post.markdown_content,
        )


__all__ = ["MediumParser"]
