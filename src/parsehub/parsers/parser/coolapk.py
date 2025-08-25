from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..base.base import Parser
from ...config import DownloadConfig, GlobalConfig
from ...types import ImageParseResult, DownloadResult, ParseError
import httpx
from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter


class CoolapkParser(Parser):
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
    def __init__(
        self, title: str, photo: list[str], desc: str, raw_url: str, coolapk: "Coolapk"
    ):
        super().__init__(title, photo, desc, raw_url)
        self.coolapk = coolapk

    async def download(
        self,
        path: str | Path = None,
        callback: Callable = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        headers = config.headers or {}
        headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        )
        config.headers = headers
        return await super().download(path, callback, callback_args, config)


@dataclass
class Coolapk:
    title: str | None = None
    markdown_content: str | None = None
    text_content: str = None
    imgs: list[str] = None

    @classmethod
    async def parse(cls, url: str, proxy: str = None) -> "Coolapk":
        async with httpx.AsyncClient(
            headers={"User-Agent": GlobalConfig.ua}, proxy=proxy
        ) as client:
            result = await client.get(url)
        soup = BeautifulSoup(result.text, "html.parser")

        title_element = soup.find(class_="message-title")
        if title_element and (title := title_element.text.strip()):
            content = soup.find(class_="feed-article-message")
            markdown_content = MarkdownConverter(heading_style="ATX").convert(
                str(content)
            )
            text_content = "".join(
                BeautifulSoup(markdown(markdown_content), "html.parser").find_all(
                    string=True
                )
            )
            imgs = [
                f"https:{i['src']}"
                for i in content.find_all("img", {"class": "message-image"})
            ]
            return cls(title, markdown_content, text_content, imgs)

        feed_element = soup.find(class_="feed-message")
        if feed_element and (content := feed_element.text.strip()):
            message_image_group = soup.find(class_="message-image-group")
            imgs = (
                [f"https:{i['src']}" for i in message_image_group.find_all("img")]
                if message_image_group
                else []
            )
            return cls(None, None, content, imgs)

        raise ValueError("获取内容失败, 分享时请保留 shareKey 或 s 参数")


__all__ = ["CoolapkParser", "CoolapkImageParseResult"]
