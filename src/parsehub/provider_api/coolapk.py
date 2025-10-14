from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter

from ..config import GlobalConfig


@dataclass
class Coolapk:
    title: str | None = None
    markdown_content: str | None = None
    text_content: str = None
    imgs: list[str] = None

    @classmethod
    async def parse(cls, url: str, proxy: str = None) -> "Coolapk":
        async with httpx.AsyncClient(headers={"User-Agent": GlobalConfig.ua}, proxy=proxy) as client:
            result = await client.get(url)
        soup = BeautifulSoup(result.text, "lxml")

        title_element = soup.find(class_="message-title")
        if title_element and (title := title_element.text.strip()):
            content = soup.find(class_="feed-article-message")
            markdown_content = MarkdownConverter(heading_style="ATX").convert(str(content))
            text_content = "".join(BeautifulSoup(markdown(markdown_content), "lxml").find_all(string=True))
            imgs = [f"https:{i['src']}" for i in content.find_all("img", {"class": "message-image"})]
            return cls(title, markdown_content, text_content, imgs)

        feed_element = soup.find(class_="feed-message")
        if feed_element and (content := feed_element.text.strip()):
            message_image_group = soup.find(class_="message-image-group")
            imgs = [f"https:{i['src']}" for i in message_image_group.find_all("img")] if message_image_group else []
            return cls(None, None, content, imgs)

        raise ValueError("获取内容失败, 分享时请保留 shareKey 或 s 参数")
