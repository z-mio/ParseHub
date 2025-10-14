from .config import ParseConfig
from .parsers.base.base import BaseParser
from .types.parse_result import ParseResult
from .utiles.utile import get_all_subclasses


class ParseHub:
    def __init__(self, config: ParseConfig = None):
        """初始化解析器"""
        self.config = config
        self.parsers: list[type[BaseParser]] = self.__load_parser()

    def select_parser(self, url: str) -> type[BaseParser] | None:
        """选择解析器"""
        for parser in self.parsers:
            if parser().match(url):
                return parser
        return None

    @staticmethod
    def __load_parser() -> list[type[BaseParser]]:
        all_subclasses = get_all_subclasses(BaseParser)
        return [subclass for subclass in all_subclasses if subclass.__match__]

    async def parse(self, url: str) -> ParseResult:
        """解析平台分享链接
        :param url: 分享链接
        """
        if parser := self.select_parser(url):
            p = parser(parse_config=self.config)
            url = await p.get_raw_url(url)
            return await p.parse(url)
        raise ValueError("不支持的平台")

    async def get_raw_url(self, url: str) -> str:
        """获取原始链接"""
        if parser := self.select_parser(url):
            return await parser(parse_config=self.config).get_raw_url(url)
        raise ValueError("不支持的平台")

    def list_parsers(self) -> list[type[BaseParser]]:
        """获取支持的解析器列表"""
        return self.parsers

    def get_supported_platforms(self) -> list[str]:
        """获取支持的平台列表"""
        return [f"{parser.__platform__}: {'|'.join(parser.__supported_type__)}" for parser in self.parsers]
