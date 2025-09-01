import re
from typing import Union, Callable, Awaitable
from pathlib import Path
import httpx
import skia
from dynamicadaptor.DynamicConversion import formate_message
from dynrender_skia.Core import DynRender

from ..base.yt_dlp_parser import YtParser, YtVideoParseResult, YtImageParseResult
from ...types.parse_result import VideoParseResult, ImageParseResult
from ...config.config import DownloadConfig, GlobalConfig
from ...types import DownloadResult, ParseError, Video, UploadError
from ...types.summary_result import SummaryResult
from ...utiles.bilibili_api import BiliAPI
from ...utiles.img_host import ImgHost
from aiofiles.tempfile import TemporaryDirectory


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
                except Exception:
                    raise ParseError("Bilibili解析失败")

    @staticmethod
    def _is_bvid(url: str):
        if url.lower().startswith("bv"):
            return True
        else:
            return False

    @staticmethod
    def get_bvid(url: str):
        m_bv = re.search(r"BV[0-9A-Za-z]{10,}", url)
        if m_bv:
            return m_bv.group(0)
        m_av = re.search(r"(?i)\bav(\d+)\b", url)
        if m_av:
            return BiliAPI.av2bv(f"av{m_av.group(1)}")
        return None

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

    async def bili_api_parse(
        self, url
    ) -> Union["BiliVideoParseResult", "BiliImageParseResult"]:
        bili = BiliAPI()
        bvid = self.get_bvid(url)
        video_info = await bili.get_video_info(bvid)

        data = video_info.get("data")
        if not data:
            raise ParseError("获取视频信息失败")
        duration = data["View"]["duration"]
        b3, b4 = await bili.get_buvid()
        if GlobalConfig.duration_limit and duration > 5400:  # 超过90分钟直接返回封面
            return BiliImageParseResult(
                title=data["View"]["title"],
                raw_url=url,
                photo=[data["View"]["pic"]],
            )
        elif GlobalConfig.duration_limit and duration > GlobalConfig.duration_limit:
            video_playurl = await bili.get_video_playurl(
                bvid, data["View"]["cid"], b3, b4, False
            )
        else:
            video_playurl = await bili.get_video_playurl(
                bvid, data["View"]["cid"], b3, b4
            )
        durl = video_playurl["data"]["durl"][0]
        video_url = (
            self.change_source(durl["backup_url"][0])
            if durl.get("backup_url")
            else durl["url"]
        )
        return BiliVideoParseResult(
            title=data["View"]["title"],
            raw_url=url,
            video=Video(video_url, thumb_url=data["View"]["pic"]),
        )

    async def ytp_parse(
        self, url
    ) -> Union["BiliYtVideoParseResult", "BiliYtImageParseResult"]:
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

    async def gen_dynamic_img(self, url: str) -> str:
        """生成动态页面的图片"""
        dyn_id = re.search(r"\b\d{18,19}\b", url).group(0)
        params = {
            "timezone_offset": "-480",
            "id": dyn_id,
            "features": "itemOpusStyle",
        }
        headers = {
            "referer": f"https://www.bilibili.com/opus/{dyn_id}",
            "user-agent": GlobalConfig.ua,
        }
        async with httpx.AsyncClient(proxy=self.cfg.proxy) as client:
            message_json = await client.get(
                "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail",
                headers=headers,
                params=params,
            )
            message_json.raise_for_status()
            mj = message_json.json()
            if not (data := mj.get("data")):
                match data.get("code"):
                    case -352:
                        raise ParseError("获取动态信息失败: -352 风控限制")
                    case _:
                        raise ParseError(f"获取动态信息失败: {mj}")
        message_formate = await formate_message("web", data.get("item"))
        img = await DynRender().run(message_formate)

        # 将渲染后的图像转换为Skia Image对象
        # noinspection PyArgumentList
        img = skia.Image.fromarray(
            array=img,
            colorType=skia.ColorType.kRGBA_8888_ColorType,
        )

        # 保存图片到临时目录
        async with TemporaryDirectory() as temp_dir:
            f = Path(temp_dir) / "temp.png"
            img.save(f.name)
            try:
                return await ImgHost(self.cfg.proxy).litterbox(f.name)
            except Exception:
                raise UploadError("图片上传图床失败")

    @staticmethod
    def change_source(url: str):
        return re.sub(r"upos-.*.bilivideo.com", "upos-sz-upcdnbda2.bilivideo.com", url)


class BiliDownloadResult(DownloadResult):
    async def summary(self, *args, **kwargs) -> SummaryResult:
        return await super().summary()
        # b站的AI总结现在需要登录, 暂时不再使用
        # bvid = self.pr.dl.raw_video_info["webpage_url_basename"]
        # r = await BiliAPI().ai_summary(bvid)
        #
        # if not r.data or r.data.code == -1:
        #     return await super().summary()
        #
        # model_result = r.data.model_result
        # text = [f"**{model_result.summary}**\n"]
        #
        # if not model_result.outline:
        #     return await super().summary()
        #
        # for i in model_result.outline:
        #     c = "\n".join(
        #         [
        #             f"__{timestamp_to_time(cc.timestamp)}__ {cc.content}"
        #             # f"__[{timestamp_to_time(cc['timestamp'])}](https://www.bilibili.com/video/{bvid}/?t={cc['timestamp']})__ {cc['content']}"
        #             for cc in i.part_outline
        #         ]
        #     )
        #     t = f"\n● **{i.title}**\n{c}"
        #     text.append(t)
        #
        # content = "\n".join(text)
        # return SummaryResult(content)


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
