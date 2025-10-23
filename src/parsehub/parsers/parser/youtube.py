from ..base.yt_dlp_parser import YtImageParseResult, YtParser, YtVideoParseResult


class YtbParse(YtParser):
    __platform_id__ = "youtube"
    __platform__ = "Youtube"
    __supported_type__ = ["视频", "音乐"]
    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\.com)?/(?!(live|post))(?!@).+"
    __redirect_keywords__ = ["m.youtube.com"]
    __reserved_parameters__ = ["v", "list", "index"]

    async def parse(self, url: str) -> YtVideoParseResult | YtImageParseResult:
        url = await self.get_raw_url(url)
        return await super().parse(url)

    @property
    def params(self):
        sub = {
            "writesubtitles": True,  # 下载字幕
            "writeautomaticsub": True,  # 下载自动生成的字幕
            "subtitlesformat": "ttml",  # 字幕格式
            # "subtitleslangs": ["en", "ja", "zh-CN"],  # 字幕语言
        }
        p = sub | super().params
        return p


__all__ = ["YtbParse"]
