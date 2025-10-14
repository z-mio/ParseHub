import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qs, urlparse

import httpx

from ...config.config import GlobalConfig, ParseConfig
from ...types import ParseError, ParseResult
from ...utiles.utile import match_url


class BaseParser(ABC):
    __platform_id__: str = None
    """平台ID"""
    __platform__: str = None
    """平台名称"""
    __supported_type__: list[str] = []
    """支持的类型, 例如: 图文, 视频, 动态"""
    __match__: str = None
    """链接匹配规则"""
    __reserved_parameters__: list[str] = []
    """要保留的参数, 例如翻页. 默认清除全部参数"""
    __redirect_keywords__: list[str] = []
    """如果链接包含其中之一, 则遵循重定向规则"""

    def __init__(self, parse_config: ParseConfig = None):
        if parse_config is None:
            parse_config = ParseConfig()
        self.cfg = parse_config

    def match(self, url: str) -> bool:
        """判断是否匹配该解析器"""
        url = match_url(url)
        return bool(re.match(self.__match__, url))

    @abstractmethod
    async def parse(self, url: str) -> ParseResult:
        """解析"""
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
