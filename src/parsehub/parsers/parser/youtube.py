import io
from typing import Any

from ...types.platform import Platform
from ..base.ytdlp import YtImageParseResult, YtParser, YtVideoParseResult


class YtbParse(YtParser):
    __platform__ = Platform.YOUTUBE
    __supported_type__ = ["视频", "音乐"]
    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\.com)?/(?!(live|post))(?!@).+"
    __redirect_keywords__ = ["m.youtube.com"]
    __reserved_parameters__ = ["v", "list", "index"]

    async def parse(self, url: str) -> YtVideoParseResult | YtImageParseResult:
        return await super().parse(url)

    @property
    def params(self):
        sub: dict[str, Any] = {
            # "writesubtitles": True, # 下载字幕
            # "writeautomaticsub": True, # 下载自动生成的字幕
            # "subtitlesformat": "ttml", # 字幕格式
            # "subtitleslangs": ["en", "ja", "zh-CN"], # 字幕语言
        }
        if self.cfg.cookie:
            sub["cookiefile"] = io.StringIO(self.to_netscape_cookie(self.cfg.cookie, "youtube.com"))
        p = sub | super().params
        return p

    @staticmethod
    def to_netscape_cookie(cookie: dict, domain: str) -> str | None:
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
