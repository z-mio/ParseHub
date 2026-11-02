from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse

from ...provider_api.bilibili import BiliAPI, BiliDynamic
from ...types import (
    ContentUnavailableError,
    DownloadResult,
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    MusicParseResult,
    MusicRef,
    ParseError,
    Platform,
    ProgressCallback,
    VideoParseResult,
    VideoRef,
)
from ...utils.helpers import UA
from ..base.base import BaseParser, FallbackStage
from ..base.ytdlp import YtParser, YtVideoParseResult


class BiliParse(BaseParser):
    __platform__ = Platform.BILIBILI
    __supported_type__ = ["视频", "动态", "音乐"]
    __match__ = r"^(http(s)?://)?((((w){3}.|(m).|(t).)?bilibili\.com)/(video|opus|audio/au\d+|\b\d{18,19}\b)|b23.tv|bili2233.cn).*"
    __reserved_parameters__ = ["p"]
    __redirect_keywords__ = ["b23.tv", "bili2233.cn"]

    async def _do_parse(
        self, raw_url: str
    ) -> YtVideoParseResult | BiliVideoParseResult | BiliMusicParseResult | ImageParseResult:
        parsed = urlparse(raw_url)
        if parsed.hostname == "mall.bilibili.com":
            raise ParseError("不支持解析商品")
        if parsed.path.startswith("/bangumi/"):
            raise ParseError("不支持解析番剧和影视")
        if BiliAPI.get_music_id(raw_url):
            return await self.bili_music_parse(raw_url)
        if await self.is_dynamic(raw_url):
            dynamic = await self.get_dynamic_info(raw_url)
            content = self.hashtag_handler(dynamic.content or "")
            photos: list[LivePhotoRef | ImageRef] = []
            if dynamic.images:
                for i in dynamic.images:
                    if i.live_url:
                        photos.append(LivePhotoRef(url=i.url, video_url=i.live_url, width=i.width, height=i.height))
                    else:
                        photos.append(ImageRef(url=i.url, width=i.width, height=i.height))
            return ImageParseResult(
                title=dynamic.title or "",
                content=content,
                photo=photos,
            )
        else:
            return await self._fallback(
                FallbackStage("API", lambda: self.bili_api_parse(raw_url)),
                FallbackStage("yt-dlp", lambda: self.ytp_parse(raw_url), cookie=bool(self.cookie)),
                stop=lambda e: False,
            )

    @staticmethod
    def _is_bvid(url: str) -> bool:
        if url.lower().startswith("bv"):
            return True
        else:
            return False

    @classmethod
    def match(cls, text: str) -> bool:
        if cls._is_bvid(text):
            return True
        else:
            return super().match(text)

    async def get_raw_url(self, url: str, **kwargs: Any) -> str:
        """获取原始链接"""
        if self._is_bvid(url):
            return f"https://www.bilibili.com/video/{url}"
        else:
            raw_url = await super().get_raw_url(url, **kwargs)
            u = urlparse(raw_url)
            q = urlencode([(k, v) for k, v in parse_qsl(u.query) if (k, v) != ("p", "1")])
            return u._replace(query=q).geturl()

    @staticmethod
    async def is_dynamic(url: str) -> str | None:
        """是动态"""
        if re.search(r"\b\d{18,19}\b", url):
            return url
        return None

    async def get_dynamic_info(self, url: str) -> BiliDynamic:
        try:
            async with BiliAPI(proxy=self.proxy) as bili:
                dynamic_info = await bili.get_dynamic_info(url, cookie=self.cookie.get_value())
        except ContentUnavailableError:
            raise
        except Exception as e:
            if "风控" in str(e):
                raise ParseError("账号风控") from e
            raise ParseError(str(e)) from e
        else:
            return cast(BiliDynamic, dynamic_info)

    async def bili_api_parse(self, url: str) -> BiliVideoParseResult | ImageParseResult:
        async with BiliAPI(proxy=self.proxy) as bili:
            video_info = await bili.get_video_info(url)

            if not (data := video_info.get("data")):
                raise ParseError("获取视频信息失败")

            p = int(parse_qs(urlparse(url).query).get("p", ["1"])[0])
            view = data["View"]

            pages = view.get("pages") or []
            page_info = next((i for i in pages if i["page"] == p), None)
            if page_info is None and pages:
                page_info = pages[0]  # p 越界时回退默认P

            cid = page_info["cid"] if page_info else view["cid"]
            duration = page_info["duration"] if page_info else view["duration"]
            dimension = page_info["dimension"] if page_info else view["dimension"]
            desc = view["desc"]

            b3, b4 = await bili.get_buvid()
            video_playurl = await bili.get_video_playurl(url, cid, b3, b4)

        durl = video_playurl["data"]["durl"][0]
        video_url = self.change_source(durl["backup_url"][0]) if durl.get("backup_url") else durl["url"]
        content = desc.strip()
        if content == "-":
            content = ""
        return BiliVideoParseResult(
            title=data["View"]["title"],
            content=content,
            video=VideoRef(
                url=video_url,
                thumb_url=data["View"]["pic"],
                duration=duration,
                width=dimension.get("width", 0),
                height=dimension.get("height", 0),
            ),
        )

    async def bili_music_parse(self, url: str) -> BiliMusicParseResult:
        async with BiliAPI(proxy=self.proxy) as bili:
            info_response = await bili.get_music_info(url)
            if not (info := info_response.get("data")):
                if info_response.get("code") == 4511001:
                    raise ContentUnavailableError("音乐未找到或已下架")
                raise ParseError(f"获取音乐信息失败: {info_response.get('message') or '未知错误'}")

            play_response = await bili.get_music_url(str(info["id"]))
            cdns: list[str] = (play_response.get("data") or {}).get("cdns") or []
            if not cdns:
                raise ParseError("获取音乐链接失败")

        return BiliMusicParseResult(
            title=info.get("title") or "",
            music=MusicRef(
                url=cdns[0],
                ext=self._music_ext(cdns[0]),
                thumb_url=info.get("cover") or None,
                backup_urls=cdns[1:],
                duration=int(info.get("duration") or 0),
            ),
            content=info.get("intro") or "",
        )

    @staticmethod
    def _music_ext(url: str) -> str:
        suffix = Path(urlparse(url).path).suffix
        return suffix.removeprefix(".") or "m4a"

    async def ytp_parse(self, url: str) -> YtVideoParseResult:
        return await BiliYtParse(proxy=self.proxy, cookie=self.cookie)._do_parse(url)

    @staticmethod
    def change_source(url: str) -> str:
        return re.sub(
            r"upos-.*.(bilivideo.com|mirrorakam.akamaized.net)",
            "upos-sz-upcdnbda2.bilivideo.com",
            url,
        )

    @staticmethod
    def hashtag_handler(desc: str) -> str:
        if not desc:
            return ""
        hashtags = re.findall(r" ?#[^#]+# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f" {hashtag.strip().removesuffix('#')} ")
        return desc.strip()


class BiliYtParse(YtParser, register=False):
    @property
    def _video_parse_result_type(self) -> type[BiliYtVideoParseResult]:
        return BiliYtVideoParseResult


class BiliYtVideoParseResult(YtVideoParseResult):
    @property
    def cli_args(self) -> list[str]:
        return [
            *super().cli_args,
            "-S",
            "+codec:h264,filesize~500M",
        ]


class BiliVideoParseResult(VideoParseResult):
    async def _do_download(
        self,
        *,
        output_dir: Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
        connections: int = 4,
        concurrency: int = 4,
    ) -> DownloadResult:
        headers = {"referer": "https://www.bilibili.com", "User-Agent": UA}
        return await super()._do_download(
            output_dir=output_dir,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            headers=headers,
            connections=connections,
            concurrency=concurrency,
        )


class BiliMusicParseResult(MusicParseResult):
    async def _do_download(
        self,
        *,
        output_dir: Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
        connections: int = 4,
        concurrency: int = 4,
    ) -> DownloadResult:
        headers = {"referer": "https://www.bilibili.com", "User-Agent": UA}
        return await super()._do_download(
            output_dir=output_dir,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            headers=headers,
            connections=connections,
            concurrency=concurrency,
        )


__all__ = [
    "BiliParse",
    "BiliVideoParseResult",
    "BiliMusicParseResult",
]
