import importlib
import pkgutil
import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from ... import parsers
from ...config.config import GlobalConfig
from ...types import AnyParseResult, ParseError
from ...types.platform import Platform
from ...utils.utils import match_url, normalize_cookie


class BaseParser(ABC):
    _registry: list[type["BaseParser"]] = []
    _registry_initialized: bool = False

    __platform__: Platform | None = None
    """平台"""
    __supported_type__: list[str] = []
    """支持的类型, 例如: 图文, 视频, 动态"""
    __match__: str | None = None
    """匹配规则"""
    __reserved_parameters__: list[str] = []
    """要保留的参数, 例如翻页. 默认清除全部参数"""
    __after_clean_parameters__: list[str] = []
    """解析完成后需要清理的参数, 在解析完成前会保留这些参数, 优先级高于 __reserved_parameters__"""
    __redirect_keywords__: list[str] = []
    """如果链接包含其中之一, 则遵循重定向规则"""

    def __init__(self, *, proxy: str | None = None, cookie: str | dict | None = None):
        self.proxy = proxy
        self.cookie = normalize_cookie(cookie)

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
        raw_url = await self.get_raw_url(url, after_clean_parameters=False)
        result = await self._do_parse(raw_url)
        result.platform = self.__platform__
        result.raw_url = self._clean_params(raw_url, self.__after_clean_parameters__)
        return result

    @abstractmethod
    async def _do_parse(self, raw_url: str) -> AnyParseResult:
        """解析
        :param raw_url: 重定向后的没有跟踪参数的原始链接
        """
        raise NotImplementedError

    async def get_raw_url(self, url: str, after_clean_parameters: bool = False) -> str:
        """
        清除链接中的参数
        :param url: 链接
        :param after_clean_parameters: 是否执行后清理参数
        :return:
        """
        url = match_url(url)
        if not url.startswith("http"):
            url = f"https://{url}"
        if any(x in url for x in self.__redirect_keywords__):
            async with httpx.AsyncClient(proxy=self.proxy, timeout=30) as client:
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
            is_reserved = i in self.__reserved_parameters__
            is_after_clean = i in self.__after_clean_parameters__
            keep = (is_reserved and not (after_clean_parameters and is_after_clean)) or (
                is_after_clean and not after_clean_parameters
            )
            if not keep:
                query_params.pop(i, None)

        new_query = urlencode(query_params, doseq=True)
        return parsed_url._replace(query=new_query).geturl()

    @staticmethod
    def _clean_params(url: str, params: list[str]) -> str:
        """清除链接中的指定参数"""
        if not params:
            return url
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        for p in params:
            query_params.pop(p, None)
        new_query = urlencode(query_params, doseq=True)
        return parsed_url._replace(query=new_query).geturl()
