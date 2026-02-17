from ...types.platform import Platform
from ..base.ytdlp import YtParser


class FacebookParse(YtParser):
    __platform__ = Platform.FACEBOOK
    __supported_type__ = ["视频"]
    __match__ = r"^(http(s)?://)?.+facebook.com/(watch\?v|share/[v,r]|.+/videos/|reel/).*"


__all__ = ["FacebookParse"]
