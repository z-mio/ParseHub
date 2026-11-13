from pathlib import PurePosixPath
from urllib.parse import urlsplit

from ...provider_api.jandan import Jandan, JandanError
from ...types import AniRef, ImageRef, ParseError, Platform, RichTextParseResult
from ..base.base import BaseParser


class JandanParser(BaseParser):
    __platform__ = Platform.JANDAN
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)?jandan\.net/(t|p)/\d+"

    @staticmethod
    def _ref(url: str) -> ImageRef | AniRef:
        """正文里的动图也是 <img>; 扩展名取自 URL."""
        suffix = PurePosixPath(urlsplit(url).path).suffix.lstrip(".").lower()
        if suffix == "gif":
            return AniRef(url=url)
        return ImageRef(url=url, ext=suffix) if suffix else ImageRef(url=url)

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
