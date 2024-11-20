from ..base.yt_dlp_parser import YtParser, YtVideoParseResult


class FacebookParse(YtParser):
    __platform__ = "Facebook"
    __supported_type__ = ["视频"]
    __match__ = r"^(http(s)?://)?.+facebook.com/(watch\?v|share/[v,r]).*"

    async def parse(self, url: str) -> "YtVideoParseResult":
        url = await self.get_raw_url(url)
        return await super().parse(url)
