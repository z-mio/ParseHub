import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union

import httpx
import skia
from aiofiles.tempfile import TemporaryDirectory
from dynamicadaptor.DynamicConversion import formate_message
from dynrender_skia.Core import DynRender

from ...config.config import DownloadConfig, GlobalConfig
from ...provider_api.bilibili import BiliAPI
from ...types import DownloadResult, ParseError, UploadError, Video
from ...types.parse_result import ImageParseResult, VideoParseResult
from ...types.summary_result import SummaryResult
from ...utiles.img_host import ImgHost
from ...utiles.utile import cookie_ellipsis, timestamp_to_time
from ..base.yt_dlp_parser import YtImageParseResult, YtParser, YtVideoParseResult


class BiliParse(YtParser):
    __platform_id__ = "bilibili"
    __platform__ = "Bilibili"
    __supported_type__ = ["视频", "动态"]
    __match__ = r"^(http(s)?://)?((((w){3}.|(m).|(t).)?bilibili\.com)/(video|opus|\b\d{18,19}\b)|b23.tv|bili2233.cn).*"
    __reserved_parameters__ = ["p"]
    __redirect_keywords__ = ["b23.tv", "bili2233.cn"]

    async def parse(
        self, url: str
    ) -> Union[
        "BiliYtVideoParseResult",
        "BiliImageParseResult",
        "BiliVideoParseResult",
        "BiliImageParseResult",
    ]:
        url = await self.get_raw_url(url)
        if ourl := await self.is_opus(url):
            photo = await self.gen_dynamic_img(ourl)
            return BiliImageParseResult(
                photo=[photo],
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

    def match(self, url: str) -> bool:
        if self._is_bvid(url):
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

    async def gen_dynamic_img(self, url: str) -> str:
        async with BiliAPI(proxy=self.cfg.proxy) as bili:
            try:
                dynamic_info = await bili.get_dynamic_info(url, cookie=self.cfg.cookie)
            except Exception as e:
                if "风控" in str(e):
                    raise ParseError(f"账号风控\n使用的cookie: {cookie_ellipsis(self.cfg.cookie)}") from e

        message_formate = await formate_message("web", dynamic_info["item"])
        img = await DynRender().run(message_formate)
        img = skia.Image.fromarray(array=img, colorType=skia.ColorType.kRGBA_8888_ColorType)
        async with TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "temp.png"
            img.save(str(f))
            try:
                async with ImgHost() as ih:
                    return await ih.zioooo(f)
            except Exception as e:
                raise UploadError("动态上传失败") from e

    async def bili_api_parse(self, url) -> Union["BiliVideoParseResult", "BiliImageParseResult"]:
        async with BiliAPI(proxy=self.cfg.proxy) as bili:
            video_info = await bili.get_video_info(url)

            if not (data := video_info.get("data")):
                raise ParseError("获取视频信息失败")

            duration = data["View"]["duration"]
            dimension = data["View"]["dimension"]
            b3, b4 = await bili.get_buvid()

            # if GlobalConfig.duration_limit and duration > 5400:  # 超过90分钟直接返回封面
            #     return BiliImageParseResult(
            #         title=data["View"]["title"],
            #         raw_url=url,
            #         photo=[data["View"]["pic"]],
            #     )
            if GlobalConfig.duration_limit and duration > GlobalConfig.duration_limit:
                video_playurl = await bili.get_video_playurl(url, data["View"]["cid"], b3, b4, False)
            else:
                video_playurl = await bili.get_video_playurl(url, data["View"]["cid"], b3, b4)

        durl = video_playurl["data"]["durl"][0]
        video_url = self.change_source(durl["backup_url"][0]) if durl.get("backup_url") else durl["url"]
        return BiliVideoParseResult(
            title=data["View"]["title"],
            raw_url=url,
            video=Video(
                video_url,
                thumb_url=data["View"]["pic"],
                duration=duration,
                width=dimension.get("width", 0),
                height=dimension.get("height", 0),
            ),
        )

    async def ytp_parse(self, url) -> Union["BiliYtVideoParseResult", "BiliYtImageParseResult"]:
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
        elif isinstance(result, YtImageParseResult):
            return BiliYtImageParseResult(
                **_d,
                photo=result.media,
            )

    @staticmethod
    def change_source(url: str):
        return re.sub(
            r"upos-.*.(bilivideo.com|mirrorakam.akamaized.net)",
            "upos-sz-upcdnbda2.bilivideo.com",
            url,
        )


class BiliDownloadResult(DownloadResult):
    async def summary(self, *args, **kwargs) -> SummaryResult:
        return await super().summary()
        # b站的AI总结现在需要登录, 暂时不再使用
        bvid = self.pr.dl.raw_video_info["webpage_url_basename"]
        r = await BiliAPI().ai_summary(bvid)

        if not r.data or r.data.code == -1:
            return await super().summary()

        model_result = r.data.model_result
        text = [f"**{model_result.summary}**\n"]

        if not model_result.outline:
            return await super().summary()

        for i in model_result.outline:
            c = "\n".join([f"__{timestamp_to_time(cc.timestamp)}__ {cc.content}" for cc in i.part_outline])
            t = f"\n● **{i.title}**\n{c}"
            text.append(t)

        content = "\n".join(text)
        return SummaryResult(content)


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
        r = await super().download(path, callback, callback_args, config)
        return BiliDownloadResult(r.pr, r.media, r.save_dir)


class BiliImageParseResult(ImageParseResult): ...


class BiliYtVideoParseResult(YtVideoParseResult):
    async def download(
        self,
        path: str | Path = None,
        callback: Callable = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        r = await super().download(path, callback, callback_args, config)
        return BiliDownloadResult(r.pr, r.media, r.save_dir)


class BiliYtImageParseResult(YtImageParseResult): ...


__all__ = [
    "BiliParse",
    "BiliDownloadResult",
    "BiliYtVideoParseResult",
    "BiliYtImageParseResult",
    "BiliVideoParseResult",
    "BiliImageParseResult",
]
