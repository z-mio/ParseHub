from ...types.platform import Platform
from ..base.ytdlp import YtParser


class Snapchatarse(YtParser):
    __platform__ = Platform.SNAPCHAT
    __supported_type__ = ["视频"]
    __match__ = r"^(http(s)?://)?(?:www\.)?snapchat\.com/@([a-zA-Z0-9._-]+)(?:/spotlight)?/([a-zA-Z0-9_-]+)"


__all__ = ["Snapchatarse"]
