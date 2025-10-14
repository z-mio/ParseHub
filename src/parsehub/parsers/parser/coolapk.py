from collections.abc import Awaitable, Callable
from pathlib import Path

from ...config import DownloadConfig
from ...provider_api.coolapk import Coolapk
from ...types import DownloadResult, ImageParseResult, ParseError
from ..base.base import BaseParser


class CoolapkParser(BaseParser):
    __platform_id__ = "coolapk"
    __platform__ = "酷安"
    __supported_type__ = ["图文"]
    __match__ = r"^(http(s)?://)www.(coolapk|coolapk1s).com/(feed|picture)/.*"
    __reserved_parameters__ = ["shareKey", "s"]
    __redirect_keywords__ = ["coolapk1s"]

    async def parse(self, url: str) -> "CoolapkImageParseResult":
        url = await self.get_raw_url(url)
        try:
            coolapk = await Coolapk.parse(url, proxy=self.cfg.proxy)
        except Exception as e:
            raise ParseError(e) from e
        return CoolapkImageParseResult(
            title=coolapk.title,
            photo=coolapk.imgs,
            desc=coolapk.text_content,
            raw_url=url,
            coolapk=coolapk,
        )


class CoolapkImageParseResult(ImageParseResult):
    def __init__(self, title: str, photo: list[str], desc: str, raw_url: str, coolapk: "Coolapk"):
        super().__init__(title, photo, desc, raw_url)
        self.coolapk = coolapk

    async def download(
        self,
        path: str | Path = None,
        callback: Callable[[int, int, str | None, tuple], Awaitable[None]] = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        headers = config.headers or {}
        headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        )
        config.headers = headers
        return await super().download(path, callback, callback_args, config)


__all__ = ["CoolapkParser", "CoolapkImageParseResult"]
