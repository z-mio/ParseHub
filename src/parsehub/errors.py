from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .utils.helpers import SecretCookie


class ParseHubError(Exception):
    MSG = __doc__
    cookie: "SecretCookie | None" = None

    def __init__(self, msg: str = "", *, cookie: "SecretCookie | None" = None):
        super().__init__(self.MSG if not msg else f"{self.MSG}: {msg}")
        self.cookie = cookie

    @property
    def message(self) -> str:
        return super().__str__()

    def __str__(self) -> str:
        return f"{self.message}\n\n使用的 Cookie: {self.cookie}" if self.cookie else self.message


class ParseError(ParseHubError):
    """解析错误"""

    MSG = __doc__


class ContentUnavailableError(ParseError):
    """作品不可用"""

    MSG = __doc__


@dataclass(frozen=True)
class FallbackAttempt:
    name: str
    error: Exception
    cookie: bool = False


def format_attempts(attempts: list[FallbackAttempt], indent: int = 0) -> str:
    lines = []
    for attempt in attempts:
        prefix = "  " * indent + f"- {attempt.name}"
        if isinstance(attempt.error, FallbackError):
            lines.append(f"{prefix}:")
            lines.append(format_attempts(attempt.error.attempts, indent + 1))
        elif isinstance(attempt.error, ParseHubError):
            lines.append(f"{prefix}: {attempt.error.message}")
            if attempt.error.cookie:
                lines.append("  " * (indent + 1) + f"使用的 Cookie: {attempt.error.cookie}")
        else:
            lines.append(f"{prefix}: {type(attempt.error).__name__}: {attempt.error}")
    return "\n".join(lines)


class FallbackError(ParseError):
    """所有解析方式均失败"""

    MSG = __doc__

    def __init__(self, attempts: list[FallbackAttempt]):
        self.attempts = attempts
        Exception.__init__(self, f"{self.MSG}:\n{format_attempts(attempts)}")


class ContentUnavailableFallbackError(FallbackError, ContentUnavailableError):
    """作品不可用"""

    MSG = __doc__


class DownloadError(ParseHubError):
    """下载错误"""

    MSG = __doc__


class DeleteError(ParseHubError):
    """删除文件错误"""

    MSG = __doc__


class UnknownPlatform(ParseHubError):
    """不支持的平台"""

    MSG = __doc__
