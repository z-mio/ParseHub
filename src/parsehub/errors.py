class ParseHubError(Exception):
    MSG = __doc__

    def __init__(self, *args):
        super().__init__(self.MSG, *args)


class ParseError(ParseHubError):
    """解析错误"""

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
