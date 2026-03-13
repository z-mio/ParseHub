from pathlib import Path

from loguru import logger

from .errors import ParseError, UnknownPlatform
from .parsers.base import BaseParser
from .types import Platform
from .types.callback import ProgressCallback
from .types.result import AnyParseResult, DownloadResult
from .utils.utils import get_event_loop

logger.disable(__name__)


class ParseHub:
    def __init__(self):
        self.parsers: list[type[BaseParser]] = BaseParser.get_registry()

    async def parse(self, url: str, *, proxy: str | None = None, cookie: str | dict | None = None) -> AnyParseResult:
        """解析
        :param url: 分享文案 / 分享链接
        :param proxy: 代理
        :param cookie: cookie
        :return: AnyParseResult
        """
        parser = self.get_parser(url)
        if not parser:
            raise UnknownPlatform(url)
        p = parser(proxy=proxy, cookie=cookie)
        return await p.parse(url)

    def parse_sync(self, url: str, *, proxy: str | None = None, cookie: str | dict | None = None) -> AnyParseResult:
        """
        同步解析
        :param url: 分享文案 / 分享链接
        :param proxy: 代理
        :param cookie: cookie
        :return: AnyParseResult
        """
        return get_event_loop().run_until_complete(self.parse(url, proxy=proxy, cookie=cookie))

    async def download(
        self,
        url: str,
        path: str | Path = None,
        *,
        callback: ProgressCallback = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        save_metadata: bool = False,
    ) -> DownloadResult:
        """下载
        :param url: 分享文案 / 分享链接
        :param path: 保存路径
        :param callback: 下载进度回调函数
        :param callback_args: 下载进度回调函数参数
        :param callback_kwargs: 回调函数的关键字参数
        :param proxy: 代理
        :param save_metadata: 保存解析结果为 metadata.json, 默认为 False
        :return: DownloadResult

        Note:
            下载进度回调函数签名::

                async def callback(current: int, total: int, unit: Literal['bytes', 'count'], *args) -> None

            - current: 当前进度值
            - total: 总进度值
            - unit: 进度单位
                - ``bytes``: 字节进度，用于单文件下载时报告已下载/总字节数
                - ``count``: 计数进度，用于多文件下载时报告已完成/总文件数
        """
        result = await self.parse(url)
        return await result.download(
            path,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
            proxy=proxy,
            save_metadata=save_metadata,
        )

    def download_sync(
        self,
        url: str,
        path: str | Path | None = None,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        save_metadata: bool = False,
    ) -> DownloadResult:
        """
        同步下载
        :param url: 分享文案 / 分享链接
        :param path: 下载路径
        :param callback: 进度回调函数
        :param callback_args: 进度回调函数参数
        :param callback_kwargs: 回调函数的关键字参数
        :param proxy: 代理
        :param save_metadata: 保存解析结果为 metadata.json, 默认为 False
        :return: DownloadResult

        Note:
            下载进度回调函数签名::

                async def callback(current: int, total: int, unit: Literal['bytes', 'count'], *args) -> None

            - current: 当前进度值
            - total: 总进度值
            - unit: 进度单位
                - ``bytes``: 字节进度，用于单文件下载时报告已下载/总字节数
                - ``count``: 计数进度，用于多文件下载时报告已完成/总文件数
        """
        return get_event_loop().run_until_complete(
            self.download(
                url,
                path,
                callback=callback,
                callback_args=callback_args,
                callback_kwargs=callback_kwargs,
                proxy=proxy,
                save_metadata=save_metadata,
            )
        )

    async def get_raw_url(self, url: str, proxy: str | None = None) -> str:
        """获取原始链接
        :param url: 分享文案 / 分享链接
        :param proxy: 代理
        :return: 原始链接
        """
        parser = self.get_parser(url)
        try:
            return await parser(proxy=proxy).get_raw_url(url)
        except Exception as e:
            raise ParseError from e

    def _select_parser(self, url: str) -> type[BaseParser] | None:
        """选择解析器
        :param url: 分享文案 / 分享链接
        """
        for parser in self.parsers:
            if parser.match(url):
                return parser
        return None

    def get_parser(self, url) -> type[BaseParser] | None:
        """获取解析器
        :param url: 分享文案 / 分享链接
        """
        if parser := self._select_parser(url):
            return parser
        return None

    def get_platform(self, url) -> Platform | None:
        """获取平台
        :param url: 分享文案 / 分享链接
        """
        if parser := self._select_parser(url):
            return parser.__platform__
        return None

    def get_platforms(self) -> list[dict]:
        """获取所有解析器的信息

        Returns:
            包含解析器信息的字典列表，每个字典包含:
            - platform: 平台id, 例: xhs
            - display_name: 平台名, 例: 小红书
            - supported_types: 支持的类型列表, 例: ['视频', '图文']
        """
        return [
            {
                "id": parser.__platform__.id,
                "name": parser.__platform__.display_name,
                "supported_types": parser.__supported_type__,
            }
            for parser in self.parsers
        ]
