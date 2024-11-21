from typing import Type

from .parsers.base.base import Parser
from .types.parse_result import ParseResult
from .utiles.utile import get_all_subclasses, match_url
from .config import ParseConfig


class ParseHub:
    def __init__(self, config: ParseConfig = None):
        """初始化解析器"""
        self.config = config
        self.__parsers: list[Type[Parser]] = self.__load_parser()

    def _select_parser(self, url: str) -> Type[Parser] | None:
        """选择解析器"""
        for parser in self.__parsers:
            if parser().match(match_url(url)):
                return parser

    @staticmethod
    def __load_parser() -> list[Type[Parser]]:
        all_subclasses = get_all_subclasses(Parser)
        return [
            subclass for subclass in all_subclasses if getattr(subclass, "__match__")
        ]

    async def parse(self, url: str) -> "ParseResult":
        """解析平台分享链接
        :param url: 分享链接
        """
        if parser := self._select_parser(url):
            return await parser(parse_config=self.config).parse(url)
        raise ValueError("不支持的平台")

    def get_supported_platforms(self) -> list[str]:
        """获取支持的平台列表"""
        return [
            f"{parser.__platform__}: {'|'.join(parser.__supported_type__)}"
            for parser in self.__parsers
        ]
