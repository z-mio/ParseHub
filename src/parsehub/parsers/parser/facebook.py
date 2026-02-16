from ...types.platform import Platform
from ..base.ytdlp import YtParser, YtVideoParseResult


class FacebookParse(YtParser):
    __platform__ = Platform.FACEBOOK
    __supported_type__ = ["视频"]
    __match__ = r"^(http(s)?://)?.+facebook.com/(watch\?v|share/[v,r]|.+/videos/|reel/).*"

    async def _do_parse(self, raw_url: str) -> YtVideoParseResult:
        return await super()._do_parse(raw_url)


__all__ = ["FacebookParse"]
