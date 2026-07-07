from ...types.platform import Platform
from ..base.ytdlp import YtParser, YtVideoParseResult


class YtbParse(YtParser):
    __platform__ = Platform.YOUTUBE
    __supported_type__ = ["视频", "音乐"]
    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\.com)?/(?!(live|post))(?!@).+"
    __redirect_keywords__ = ["m.youtube.com"]
    __reserved_parameters__ = ["v", "list", "index"]

    @property
    def _video_parse_result_type(self) -> type["YtbVideoParseResult"]:
        return YtbVideoParseResult

    def get_cookie_text(self) -> str | None:
        if cookie := self.cookie.get_value():
            return self.to_netscape_cookie(cookie, "youtube.com")
        return None

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


class YtbVideoParseResult(YtVideoParseResult):
    @property
    def cli_args(self) -> list[str]:
        return [
            *super().cli_args,
            "-S",
            "+codec:h264,filesize~500M",
            # "--write-subs", # 下载字幕
            # "--write-auto-subs", # 下载自动生成的字幕
            # "--sub-format", "ttml", # 字幕格式
            # "--sub-langs", "en,ja,zh-CN", # 字幕语言
        ]


__all__ = ["YtbParse"]
