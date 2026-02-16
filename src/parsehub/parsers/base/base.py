import importlib
import pkgutil
import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qs, urlparse

import httpx

from ... import parsers
from ...config.config import GlobalConfig, ParseConfig
from ...types import AnyParseResult, ParseError
from ...types.platform import Platform
from ...utils.util import match_url


class BaseParser(ABC):
    _registry: list[type["BaseParser"]] = []
    _registry_initialized: bool = False

    __platform__: Platform = None
    """平台"""
    __supported_type__: list[str] = []
    """支持的类型, 例如: 图文, 视频, 动态"""
    __match__: str = None
    """匹配规则"""
    __reserved_parameters__: list[str] = []
    """要保留的参数, 例如翻页. 默认清除全部参数"""
    __redirect_keywords__: list[str] = []
    """如果链接包含其中之一, 则遵循重定向规则"""

    def __init__(self, config: ParseConfig = None):
        if config is None:
            config = ParseConfig()
        self.cfg = config

    def __init_subclass__(cls, /, register=True, **kwargs):
        super().__init_subclass__(**kwargs)
        if register:
            if not cls.__platform__:
                raise ValueError(
                    f"解析器未指定平台: {cls}, 如果不是平台请使用 register=False, "
                    f"例: class {cls.__name__}({BaseParser.__name__}, register=False): ..."
                )
            cls._registry.append(cls)

    @classmethod
    def get_registry(cls) -> list[type["BaseParser"]]:
        if not cls._registry_initialized:
            for _, name, _ in pkgutil.walk_packages(parsers.__path__, f"{parsers.__name__}."):
                importlib.import_module(name)
            cls._registry_initialized = True
        return cls._registry.copy()

    @classmethod
    def match(cls, text: str) -> bool:
        """判断是否匹配该解析器"""
        url = match_url(text)
        return bool(re.match(cls.__match__, url))

    async def parse(self, url: str) -> AnyParseResult:
        """解析
        :param url: 分享文案 / 分享链接
        :return: 解析结果
        """
        raw_url = await self.get_raw_url(url)
        result = await self._do_parse(raw_url)
        result.platform = self.__platform__
        return result

    @abstractmethod
    async def _do_parse(self, raw_url: str) -> AnyParseResult:
        """解析
        :param raw_url: 重定向后的没有跟踪参数的原始链接
        """
        raise NotImplementedError

    async def get_raw_url(self, url: str) -> str:
        """
        清除链接中的参数
        :param url: 链接
        :return:
        """
        url = match_url(url)
        if not url.startswith("http"):
            url = f"https://{url}"
        if any(x in url for x in self.__redirect_keywords__):
            async with httpx.AsyncClient(proxy=self.cfg.proxy, timeout=30) as client:
                try:
                    r = await client.get(
                        url,
                        follow_redirects=True,
                        headers={"User-Agent": GlobalConfig.ua},
                    )
                    r.raise_for_status()
                except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                    raise ParseError("获取原始链接超时") from e
                except Exception as e:
                    raise ParseError("获取原始链接失败") from e
                url = str(r.url)

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        for i in query_params.copy().keys():
            if i not in self.__reserved_parameters__:
                del query_params[i]
        new_query = "&".join([f"{k}={v[0]}" for k, v in query_params.items()])
        return parsed_url._replace(query=new_query).geturl()
