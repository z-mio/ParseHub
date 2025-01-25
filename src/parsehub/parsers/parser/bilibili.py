import re
from typing import Union, Callable
from pathlib import Path
import httpx
import skia
from dynamicadaptor.DynamicConversion import formate_message
from dynrender_skia.Core import DynRender

from ..base.yt_dlp_parser import YtParser, YtVideoParseResult, YtImageParseResult
from ...config.config import DownloadConfig
from ...types import DownloadResult
from ...types.summary_result import SummaryResult
from ...utiles.bilibili_api import BiliAPI
from ...utiles.utile import timestamp_to_time
from ...utiles.img_host import ImgHost
from aiofiles.tempfile import TemporaryDirectory


class BiliParse(YtParser):
    __platform__ = "Bilibili"
    __supported_type__ = ["视频", "动态"]
    __match__ = r"^(http(s)?://)?((((w){3}.|(m).|(t).)?bilibili\.com)/(video|opus|\b\d{18,19}\b)|b23.tv|bili2233.cn).*"
    __reserved_parameters__ = ["p"]
    __redirect_keywords__ = ["b23.tv", "bili2233.cn"]

    async def parse(
        self, url: str
    ) -> Union["BiliVideoParseResult", "BiliImageParseResult"]:
        url = await self.get_raw_url(url)
        if ourl := await self.is_opus(url):
            photo = await self.gen_dynamic_img(ourl)
            return BiliImageParseResult(
                photo=[photo],
                raw_url=ourl,
            )
        else:
            result = await super().parse(url)
            _d = {
                "title": result.title,
                "raw_url": result.raw_url,
                "dl": result.dl,
            }
            if isinstance(result, YtVideoParseResult):
                return BiliVideoParseResult(
                    **_d,
                    video=result.media,
                )
            elif isinstance(result, YtImageParseResult):
                return BiliImageParseResult(
                    **_d,
                    photo=result.media,
                )

    async def gen_dynamic_img(self, dyn: str) -> str:
        """生成动态页面的图片"""
        dyn_id = re.search(r"\b\d{18,19}\b", dyn).group(0)
        url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?timezone_offset=-480&id={dyn_id}&features=itemOpusStyle"
        headers = {
            "referer": f"https://t.bilibili.com/{dyn_id}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        async with httpx.AsyncClient(proxies=self.cfg.proxy) as client:
            message_json = await client.get(url, headers=headers)

        message_formate = await formate_message(
            "web", message_json.json()["data"]["item"]
        )
        img = await DynRender().run(message_formate)

        # 将渲染后的图像转换为Skia Image对象
        img = skia.Image.fromarray(
            array=img,
            colorType=skia.ColorType.kRGBA_8888_ColorType,
        )

        # 保存图片到临时目录
        async with TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "temp.png"
            img.save(f.name)
            return await ImgHost(self.cfg.proxy).litterbox(f.name)

    async def is_opus(self, url) -> str:
        """是动态"""
        async with httpx.AsyncClient(proxies=self.cfg.proxy) as cli:
            url = str((await cli.get(url, follow_redirects=True)).url)
        try:
            if bool(re.search(r"\b\d{18,19}\b", url).group(0)):
                return url
        except AttributeError:
            ...


class BiliDownloadResult(DownloadResult):
    async def summary(self, *args, **kwargs) -> SummaryResult:
        bvid = self.pr.dl.raw_video_info["webpage_url_basename"]
        r = await BiliAPI().ai_summary(bvid)

        if not r.data or r.data.code == -1:
            # return SummaryResult("此视频不存在AI总结")
            return await super().summary()

        model_result = r.data.model_result
        text = [f"**{model_result.summary}**\n"]

        if not model_result.outline:
            return await super().summary()

        for i in model_result.outline:
            c = "\n".join(
                [
                    f"__{timestamp_to_time(cc.timestamp)}__ {cc.content}"
                    # f"__[{timestamp_to_time(cc['timestamp'])}](https://www.bilibili.com/video/{bvid}/?t={cc['timestamp']})__ {cc['content']}"
                    for cc in i.part_outline
                ]
            )
            t = f"\n● **{i.title}**\n{c}"
            text.append(t)

        content = "\n".join(text)
        return SummaryResult(content)


class BiliVideoParseResult(YtVideoParseResult):
    async def download(
        self,
        path: str | Path = None,
        callback: Callable = None,
        callback_args: tuple = (),
        config: DownloadConfig = DownloadConfig(),
    ) -> DownloadResult:
        r = await super().download(path, callback, callback_args, config)
        return BiliDownloadResult(r.pr, r.media, r.save_dir)


class BiliImageParseResult(YtImageParseResult): ...
