import io
from typing import Any

from ...types.platform import Platform
from ..base.ytdlp import YtParser


class YtbParse(YtParser):
    __platform__ = Platform.YOUTUBE
    __supported_type__ = ["视频", "音乐"]
    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\.com)?/(?!(live|post))(?!@).+"
    __redirect_keywords__ = ["m.youtube.com"]
    __reserved_parameters__ = ["v", "list", "index"]

    @property
    def params(self) -> dict[str, Any]:
        sub: dict[str, Any] = {
            "format": "mp4+bestvideo[res<=1080]+bestaudio/mp4+bestvideo+bestaudio/mp4+best",
            # "writesubtitles": True, # 下载字幕
            # "writeautomaticsub": True, # 下载自动生成的字幕
            # "subtitlesformat": "ttml", # 字幕格式
            # "subtitleslangs": ["en", "ja", "zh-CN"], # 字幕语言
        }
        if cookie := self.cookie.get_value():
            sub["cookiefile"] = io.StringIO(self.to_netscape_cookie(cookie, "youtube.com"))
        p = sub | super().params
        return p

    @staticmethod
    def to_netscape_cookie(cookie: dict | None, domain: str) -> str | None:
        """将字典格式 cookie 转为 Netscape 格式字符串
        :param cookie: 字典格式 cookie
        :param domain: cookie 所属域名, 例如 "youtube.com"
        """
        if not cookie:
            return None
        if not domain.startswith("."):
            domain = f".{domain}"
        lines = ["# Netscape HTTP Cookie File"]
        for name, value in cookie.items():
            lines.append(f"{domain}\tTRUE\t/\tFALSE\t0\t{name}\t{value}")
        return "\n".join(lines) + "\n"


__all__ = ["YtbParse"]
