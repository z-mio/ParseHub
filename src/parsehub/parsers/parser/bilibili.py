import re
from pathlib import Path
from typing import Union
from urllib.parse import parse_qs, urlparse

from loguru import logger

from ...config.config import GlobalConfig
from ...provider_api.bilibili import BiliAPI, BiliDynamic
from ...types import (
    DownloadResult,
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    ParseError,
    Platform,
    ProgressCallback,
    VideoParseResult,
    VideoRef,
)
from ...utils.utils import cookie_ellipsis
from ..base.ytdlp import YtParser, YtVideoParseResult


class BiliParse(YtParser):
    __platform__ = Platform.BILIBILI
    __supported_type__ = ["视频", "动态"]
    __match__ = r"^(http(s)?://)?((((w){3}.|(m).|(t).)?bilibili\.com)/(video|opus|\b\d{18,19}\b)|b23.tv|bili2233.cn).*"
    __reserved_parameters__ = ["p"]
    __redirect_keywords__ = ["b23.tv", "bili2233.cn"]

    async def _do_parse(self, raw_url: str) -> Union["YtVideoParseResult", "BiliVideoParseResult", ImageParseResult]:
        if await self.is_dynamic(raw_url):
            dynamic = await self.get_dynamic_info(raw_url)
            content = self.hashtag_handler(dynamic.content)
            photos = []
            if dynamic.images:
                for i in dynamic.images:
                    if i.live_url:
                        photos.append(LivePhotoRef(url=i.url, video_url=i.live_url, width=i.width, height=i.height))
                    else:
                        photos.append(ImageRef(url=i.url, width=i.width, height=i.height))
            return ImageParseResult(
                title=dynamic.title,
                content=content,
                photo=photos,
            )
        else:
            try:
                return await self.bili_api_parse(raw_url)
            except Exception as e:
                logger.opt(exception=e).warning("Bilibili API 解析失败, 尝试 yt-dlp 解析")
                try:
                    return await self.ytp_parse(raw_url)
                except Exception as e:
                    raise ParseError("Bilibili 解析失败") from e

    @staticmethod
    def _is_bvid(url: str):
        if url.lower().startswith("bv"):
            return True
        else:
            return False

    @classmethod
    def match(cls, url: str) -> bool:
        if cls._is_bvid(url):
            return True
        else:
            return super().match(url)

    async def get_raw_url(self, url: str, clean_all: bool = False) -> str:
        """获取原始链接"""
        if self._is_bvid(url):
            return f"https://www.bilibili.com/video/{url}"
        else:
            return await super().get_raw_url(url, clean_all=clean_all)

    @staticmethod
    async def is_dynamic(url) -> str | None:
        """是动态"""
        if re.search(r"\b\d{18,19}\b", url):
            return url
        return None

    async def get_dynamic_info(self, url: str) -> BiliDynamic:
        async with BiliAPI(proxy=self.proxy) as bili:
            try:
                dynamic_info = await bili.get_dynamic_info(url, cookie=self.cookie)
            except Exception as e:
                if "风控" in str(e):
                    raise ParseError(f"账号风控\n使用的cookie: {cookie_ellipsis(self.cookie)}") from e
                raise ParseError(str(e)) from e
        return dynamic_info

    async def bili_api_parse(self, url) -> Union["BiliVideoParseResult", "ImageParseResult"]:
        async with BiliAPI(proxy=self.proxy) as bili:
            video_info = await bili.get_video_info(url)

            if not (data := video_info.get("data")):
                raise ParseError("获取视频信息失败")

            p = int(parse_qs(urlparse(url).query).get("p", ["1"])[0])
            view = data["View"]

            cid = view["cid"]
            part = ""
            duration = view["duration"]
            dimension = view["dimension"]

            if p != 1 and (pages := view.get("pages")):
                if page_info := next((i for i in pages if i["page"] == p), None):
                    cid = page_info["cid"]
                    part = page_info["part"]
                    duration = page_info["duration"]
                    dimension = page_info["dimension"]

            b3, b4 = await bili.get_buvid()
            video_playurl = await bili.get_video_playurl(url, cid, b3, b4)
            # if GlobalConfig.duration_limit and duration > GlobalConfig.duration_limit:
            #     video_playurl = await bili.get_video_playurl(url, cid, b3, b4, False)
            # else:
            #     video_playurl = await bili.get_video_playurl(url, cid, b3, b4)

        durl = video_playurl["data"]["durl"][0]
        video_url = self.change_source(durl["backup_url"][0]) if durl.get("backup_url") else durl["url"]
        return BiliVideoParseResult(
            title=data["View"]["title"],
            content=f"P{p}: {part}" if part else "",
            video=VideoRef(
                url=video_url,
                thumb_url=data["View"]["pic"],
                duration=duration,
                width=dimension.get("width", 0),
                height=dimension.get("height", 0),
            ),
        )

    async def ytp_parse(self, url) -> Union["YtVideoParseResult"]:
        result = await super()._do_parse(url)
        return YtVideoParseResult(
            title=result.title,
            dl=result.dl,
            video=result.media,
        )

    @staticmethod
    def change_source(url: str):
        return re.sub(
            r"upos-.*.(bilivideo.com|mirrorakam.akamaized.net)",
            "upos-sz-upcdnbda2.bilivideo.com",
            url,
        )

    @staticmethod
    def hashtag_handler(desc: str | None) -> str | None:
        if not desc:
            return None
        hashtags = re.findall(r" ?#[^#]+# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f" {hashtag.strip().removesuffix('#')} ")
        return desc.strip()


class BiliVideoParseResult(VideoParseResult):
    async def _do_download(
        self,
        *,
        output_dir: str | Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
    ) -> "DownloadResult":
        headers = {"referer": "https://www.bilibili.com", "User-Agent": GlobalConfig.ua}
        return await super()._do_download(
            output_dir=output_dir,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            headers=headers,
        )


__all__ = [
    "BiliParse",
    "BiliVideoParseResult",
]
