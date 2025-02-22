from typing import Union

from ..base.yt_dlp_parser import YtParser, YtVideoParseResult, YtImageParseResult


class YtbParse(YtParser):
    __platform__ = "Youtube"
    __supported_type__ = ["视频", "音乐"]
    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\.com)?/(?!live)(?!@).+"
    __reserved_parameters__ = ["v", "list", "index"]

    async def parse(
        self, url: str
    ) -> Union["YtVideoParseResult", "YtImageParseResult"]:
        url = await self.get_raw_url(url)

        return await super().parse(url)

    @property
    def params(self):
        sub = {
            "writesubtitles": True,  # 下载字幕
            "writeautomaticsub": True,  # 下载自动翻译的字幕
            "subtitlesformat": "ttml",  # 字幕格式
            # "subtitleslangs": ["en", "ja", "zh-CN"],  # 字幕语言
        }
        p = sub | super().params
        # p.pop("proxy", None)
        return p
