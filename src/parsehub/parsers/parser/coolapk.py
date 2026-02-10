from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union

from ...config import DownloadConfig
from ...provider_api.coolapk import Coolapk
from ...types import (
    Ani,
    DownloadResult,
    Image,
    ImageParseResult,
    MultimediaParseResult,
    ParseError,
    ParseResult,
    RichTextParseResult,
)
from ...types.platform import Platform
from ...utiles.utile import clear_params
from ..base.base import BaseParser


class CoolapkParser(BaseParser):
    __platform__ = Platform.COOLAPK
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)www.coolapk.com/(feed|picture)/.*"
    __reserved_parameters__ = ["shareKey", "s"]

    async def parse(
        self, url: str
    ) -> Union["CoolapkImageParseResult", "CoolapkRichTextParseResult", "CoolapkMultimediaParseResult"]:
        raw_url = clear_params(url, ["s", "shareKey"])
        try:
            coolapk = await Coolapk.parse(url, proxy=self.cfg.proxy)
        except Exception as e:
            raise ParseError(e) from e
        media = [Ani(i) if ".gif" in i else Image(i) for i in coolapk.imgs]
        if coolapk.markdown_content:
            return CoolapkRichTextParseResult(
                title=coolapk.title,
                media=media,
                markdown_content=coolapk.markdown_content,
                raw_url=raw_url,
            )
        if any(isinstance(m, Ani) for m in media):
            return CoolapkMultimediaParseResult(
                title=coolapk.title,
                media=media,
                content=coolapk.text_content,
                raw_url=raw_url,
            )
        return CoolapkImageParseResult(
            title=coolapk.title,
            photo=media,
            content=coolapk.text_content,
            raw_url=raw_url,
        )


class CoolapkParseResult(ParseResult):
    async def download(
        self,
        path: str | Path = None,
        callback: Callable[[int, int, str | None, tuple], Awaitable[None]] = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        headers = config.headers or {}
        headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,"
            "*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        )
        config.headers = headers
        return await super().download(path, callback, callback_args, config)


class CoolapkImageParseResult(ImageParseResult, CoolapkParseResult): ...


class CoolapkMultimediaParseResult(MultimediaParseResult, CoolapkParseResult): ...


class CoolapkRichTextParseResult(RichTextParseResult, CoolapkParseResult): ...


__all__ = ["CoolapkParser", "CoolapkImageParseResult", "CoolapkMultimediaParseResult", "CoolapkRichTextParseResult"]
