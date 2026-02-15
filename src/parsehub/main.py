import importlib
import pkgutil

from . import parsers
from .config import ParseConfig
from .parsers.base.base import BaseParser
from .types.result import AnyParseResult


class ParseHub:
    def __init__(self, config: ParseConfig = None):
        """初始化解析器"""
        self.config = config
        self.parsers: list[type[BaseParser]] = self.__load_parser()

    def select_parser(self, url: str) -> type[BaseParser] | None:
        """选择解析器"""
        for parser in self.parsers:
            if parser.match(url):
                return parser
        return None

    @staticmethod
    def __load_parser() -> list[type[BaseParser]]:
        def get_all_subclasses(cls):
            for _, module_name, _ in pkgutil.walk_packages(parsers.__path__, f"{parsers.__name__}."):
                importlib.import_module(module_name)

            subclasses = set(cls.__subclasses__())
            for subclass in cls.__subclasses__():
                subclasses.update(get_all_subclasses(subclass))
            return subclasses

        all_subclasses = get_all_subclasses(BaseParser)
        return [s for s in all_subclasses if s.__match__]

    async def parse(self, url: str) -> AnyParseResult:
        """解析平台分享链接
        :param url: 分享链接
        """
        parser = self.select_parser(url)
        if not parser:
            raise ValueError("不支持的平台")

        p = parser(parse_config=self.config)
        url = await p.get_raw_url(url)
        result = await p.parse(url)
        result.platform = parser.__platform__
        return result

    async def get_raw_url(self, url: str) -> str:
        """获取原始链接"""
        if parser := self.select_parser(url):
            return await parser(parse_config=self.config).get_raw_url(url)
        raise ValueError("不支持的平台")

    def get_supported_platforms(self) -> list[str]:
        """获取支持的平台列表"""
        return [f"{parser.__platform__.display_name}: {'|'.join(parser.__supported_type__)}" for parser in self.parsers]
