import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union
from urllib.parse import parse_qs, urlparse

import httpx

from ...config.config import DownloadConfig, GlobalConfig
from ...provider_api.bilibili import BiliAPI, BiliDynamic
from ...types import DownloadResult, ImageRef, LivePhotoRef, ParseError, VideoRef
from ...types.platform import Platform
from ...types.result import ImageParseResult, VideoParseResult
from ...utils.util import cookie_ellipsis
from ..base.ytdlp import YtParser, YtVideoParseResult


class BiliParse(YtParser):
    __platform__ = Platform.BILIBILI
    __supported_type__ = ["视频", "动态"]
    __match__ = r"^(http(s)?://)?((((w){3}.|(m).|(t).)?bilibili\.com)/(video|opus|\b\d{18,19}\b)|b23.tv|bili2233.cn).*"
    __reserved_parameters__ = ["p"]
    __redirect_keywords__ = ["b23.tv", "bili2233.cn"]

    async def parse(self, url: str) -> Union["BiliYtVideoParseResult", "BiliVideoParseResult", ImageParseResult]:
        if ourl := await self.is_opus(url):
            dynamic = await self.get_dynamic_info(ourl)
            photos = []
            if dynamic.images:
                for i in dynamic.images:
                    if i.live_url:
                        photos.append(LivePhotoRef(url=i.url, video_url=i.live_url, width=i.width, height=i.height))
                    else:
                        photos.append(ImageRef(url=i.url, width=i.width, height=i.height))
            return ImageParseResult(
                title=dynamic.title,
                content=dynamic.content,
                photo=photos,
                raw_url=ourl,
            )
        else:
            try:
                return await self.bili_api_parse(url)
            except Exception:
                try:
                    return await self.ytp_parse(url)
                except Exception as e:
                    raise ParseError("Bilibili解析失败") from e

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

    async def get_raw_url(self, url: str) -> str:
        """获取原始链接"""
        if self._is_bvid(url):
            return f"https://www.bilibili.com/video/{url}"
        else:
            return await super().get_raw_url(url)

    async def is_opus(self, url) -> str | None:
        """是动态"""
        async with httpx.AsyncClient(proxy=self.cfg.proxy) as cli:
            url = str((await cli.get(url, follow_redirects=True, timeout=30)).url)
        try:
            if bool(re.search(r"\b\d{18,19}\b", url).group(0)):
                return url
        except AttributeError:
            ...

    async def get_dynamic_info(self, url: str) -> BiliDynamic:
        async with BiliAPI(proxy=self.cfg.proxy) as bili:
            try:
                dynamic_info = await bili.get_dynamic_info(url, cookie=self.cfg.cookie)
            except Exception as e:
                if "风控" in str(e):
                    raise ParseError(f"账号风控\n使用的cookie: {cookie_ellipsis(self.cfg.cookie)}") from e
        return dynamic_info

    async def bili_api_parse(self, url) -> Union["BiliVideoParseResult", "ImageParseResult"]:
        async with BiliAPI(proxy=self.cfg.proxy) as bili:
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
            if GlobalConfig.duration_limit and duration > GlobalConfig.duration_limit:
                video_playurl = await bili.get_video_playurl(url, cid, b3, b4, False)
            else:
                video_playurl = await bili.get_video_playurl(url, cid, b3, b4)

        durl = video_playurl["data"]["durl"][0]
        video_url = self.change_source(durl["backup_url"][0]) if durl.get("backup_url") else durl["url"]
        return BiliVideoParseResult(
            title=data["View"]["title"],
            raw_url=url,
            content=f"P{p}: {part}" if part else "",
            video=VideoRef(
                url=video_url,
                thumb_url=data["View"]["pic"],
                duration=duration,
                width=dimension.get("width", 0),
                height=dimension.get("height", 0),
            ),
        )

    async def ytp_parse(self, url) -> Union["BiliYtVideoParseResult"]:
        result = await super().parse(url)
        _d = {
            "title": result.title,
            "raw_url": result.raw_url,
            "dl": result.dl,
        }
        if isinstance(result, YtVideoParseResult):
            return BiliYtVideoParseResult(
                **_d,
                video=result.media,
            )
        else:
            raise ValueError(f"Unsupported result type: {type(result)}")

    @staticmethod
    def change_source(url: str):
        return re.sub(
            r"upos-.*.(bilivideo.com|mirrorakam.akamaized.net)",
            "upos-sz-upcdnbda2.bilivideo.com",
            url,
        )


class BiliVideoParseResult(VideoParseResult):
    async def download(
        self,
        path: str | Path = None,
        callback: Callable[[int, int, str | None, tuple], Awaitable[None]] = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> "DownloadResult":
        headers = config.headers or {}
        headers["referer"] = "https://www.bilibili.com"
        headers["User-Agent"] = GlobalConfig.ua
        config.headers = headers
        return await super().download(path, callback, callback_args, config)


class BiliYtVideoParseResult(YtVideoParseResult):
    async def download(
        self,
        path: str | Path = None,
        callback: Callable = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        return await super().download(path, callback, callback_args, config)


__all__ = [
    "BiliParse",
    "BiliYtVideoParseResult",
    "BiliVideoParseResult",
]
