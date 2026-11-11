from urllib.parse import urlsplit

from ...provider_api.jandan import Jandan, JandanError
from ...types import AniRef, ImageRef, ParseError, Platform, RichTextParseResult
from ..base.base import BaseParser

_IMAGE_EXTENSIONS = {"avif", "bmp", "gif", "heic", "heif", "jpeg", "jpg", "png", "tif", "tiff", "webp"}


class JandanParser(BaseParser):
    __platform__ = Platform.JANDAN
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)?jandan\.net/(t|p)/\d+"

    @staticmethod
    def _ref(url: str) -> ImageRef | AniRef:
        """正文里的动图也是 <img>; 扩展名取自 URL."""
        suffix = urlsplit(url).path.rpartition(".")[2].lower()
        if suffix not in _IMAGE_EXTENSIONS:
            suffix = "jpg"
        return AniRef(url=url) if suffix == "gif" else ImageRef(url=url, ext=suffix)

    async def _do_parse(self, raw_url: str) -> RichTextParseResult:
        try:
            post = await Jandan(proxy=self.proxy).parse(raw_url)
        except JandanError as e:
            raise ParseError(f"煎蛋解析失败: {e}") from e

        return RichTextParseResult(
            title=post.title,
            media=[self._ref(url) for url in post.images],
            markdown_content=post.markdown_content,
        )


__all__ = ["JandanParser"]
