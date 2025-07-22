from dataclasses import dataclass
from typing import Union

import httpx
from bs4 import BeautifulSoup
from httpx import Response

from ..base.base import Parser
from ...types import VideoParseResult, ImageParseResult, ParseError


class TieBaParser(Parser):
    __platform__ = "贴吧"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+tieba.baidu.com/p/\d+"

    async def parse(self, url: str) -> Union["ImageParseResult", "VideoParseResult"]:
        try:
            tb = await TieBa(self.cfg.proxy).parse(url)
        except Exception as e:
            raise ParseError("贴吧解析失败") from e

        if tb.video_url:
            return VideoParseResult(
                title=tb.title, video=tb.video_url, raw_url=url, desc=tb.content
            )
        else:
            return ImageParseResult(
                title=tb.title, photo=tb.img_url, raw_url=url, desc=tb.content
            )


class TieBa:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    @staticmethod
    def _parse_out_the_body(text):
        soup = BeautifulSoup(str(text), "html.parser")
        div_tag = soup.find_all("div")
        [img.extract() for img in soup.find_all("img")]
        [i.unwrap() for i in div_tag]
        text = soup.text.strip()
        # text = re.sub(
        #     r"(<br/><br/>)+|点击展开，查看完整图片|<i.*></i>", "", str(soup)
        # ).strip()
        # text = re.sub(r'<span class="apc_src_wrapper">视频来自：.*</span>', "", text)
        return text

    @staticmethod
    async def get_tieba_img_url(html: Response):
        """获取帖子中所有图片的URL"""
        soup = BeautifulSoup(html.text, "html.parser")
        d_post_content_firstfloor = soup.find(
            "div", {"class": "d_post_content_firstfloor"}
        )
        img_tags = d_post_content_firstfloor.find_all("img", {"class": "BDE_Image"})
        return [img["src"] for img in img_tags if "src" in img.attrs]

    @staticmethod
    async def get_tieba_video_url(html: Response):
        """获取帖子中所有视频的URL"""
        soup = BeautifulSoup(html.text, "html.parser")
        d_post_content_firstfloor = soup.find(
            "div", {"class": "d_post_content_firstfloor"}
        )

        if video_tags := d_post_content_firstfloor.find(
            "embed", {"class": "BDE_Flash"}
        ):
            return video_tags["data-video"]
        return None

    async def get_the_content(self, html: Response):
        """获取帖子的标题和内容"""
        soup = BeautifulSoup(html.text, "html.parser")
        title = soup.find(
            "h3", {"class": ["core_title_txt", "pull-left", "text-overflow"]}
        ) or soup.find("h1", {"class": "core_title_txt"})
        if not title:
            raise Exception("未获取到标题内容")
        title = title.text.strip()
        content = soup.find("div", {"class": ["d_post_content", "j_d_post_content"]})
        content = self._parse_out_the_body(content)
        return title, content

    async def get_html(self, t_url) -> Response:
        async with httpx.AsyncClient(proxy=self.proxy) as c:
            return await c.get(t_url, headers={"User-Agent": "Mozilla5.0/"}, timeout=15)

    async def parse(self, t_url) -> "TieBaPost":
        res = await self.get_html(t_url)

        title, content = await self.get_the_content(res)
        img_url = await self.get_tieba_img_url(res)
        video_url = await self.get_tieba_video_url(res)
        return TieBaPost(title, content, img_url, video_url)


@dataclass
class TieBaPost:
    title: str
    content: str
    img_url: list
    video_url: str = None
