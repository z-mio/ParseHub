from pathlib import Path
from typing import Union

from ...provider_api.coolapk import Coolapk
from ...types import (
    AniRef,
    DownloadResult,
    ImageParseResult,
    ImageRef,
    MultimediaParseResult,
    ParseError,
    ParseResult,
    Platform,
    ProgressCallback,
    RichTextParseResult,
)
from ...utils.utils import clear_params
from ..base.base import BaseParser


class CoolapkParser(BaseParser):
    __platform__ = Platform.COOLAPK
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)www.coolapk.com/(feed|picture)/.*"
    __reserved_parameters__ = ["shareKey", "s"]

    async def _do_parse(
        self, raw_url: str
    ) -> Union["CoolapkImageParseResult", "CoolapkRichTextParseResult", "CoolapkMultimediaParseResult"]:
        raw_url_ = clear_params(raw_url, ["s", "shareKey"])
        try:
            coolapk = await Coolapk.parse(raw_url, proxy=self.cfg.proxy)
        except Exception as e:
            raise ParseError(str(e)) from e
        media = [AniRef(url=i) if ".gif" in i else ImageRef(url=i) for i in coolapk.imgs]
        if coolapk.markdown_content:
            return CoolapkRichTextParseResult(
                title=coolapk.title,
                media=media,
                markdown_content=coolapk.markdown_content,
                raw_url=raw_url_,
            )
        if any(isinstance(m, AniRef) for m in media):
            return CoolapkMultimediaParseResult(
                title=coolapk.title,
                media=media,
                content=coolapk.text_content,
                raw_url=raw_url_,
            )
        return CoolapkImageParseResult(
            title=coolapk.title,
            photo=media,
            content=coolapk.text_content,
            raw_url=raw_url_,
        )


class CoolapkParseResult(ParseResult):
    async def _do_download(
        self,
        *,
        output_dir: str | Path,
        callback: ProgressCallback = None,
        callback_args: tuple = (),
        proxy: str | None = None,
        headers: dict = None,
    ) -> "DownloadResult":
        headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,"
                "*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            )
        }
        return await super()._do_download(
            output_dir=output_dir, callback=callback, callback_args=callback_args, proxy=proxy, headers=headers
        )


class CoolapkImageParseResult(ImageParseResult, CoolapkParseResult): ...


class CoolapkMultimediaParseResult(MultimediaParseResult, CoolapkParseResult): ...


class CoolapkRichTextParseResult(RichTextParseResult, CoolapkParseResult): ...


__all__ = ["CoolapkParser", "CoolapkImageParseResult", "CoolapkMultimediaParseResult", "CoolapkRichTextParseResult"]
