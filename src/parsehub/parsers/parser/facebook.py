from typing import Any

from ...types.platform import Platform
from ..base.ytdlp import YtParser


class FacebookParse(YtParser):
    __platform__ = Platform.FACEBOOK
    __supported_type__ = ["视频"]
    __match__ = r"^(http(s)?://)?.+facebook.com/(watch\?v|share/[v,r]|.+/videos/|reel/).*"

    @property
    def params(self) -> dict[str, Any]:
        p = super().params.copy()
        p.pop('format')
        return p


__all__ = ["FacebookParse"]
