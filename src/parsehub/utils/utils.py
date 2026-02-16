import asyncio
import re
from urllib.parse import parse_qs, urlparse

from urlextract import URLExtract


def get_event_loop():
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
    return event_loop


def match_url(text: str) -> str:
    """从文本中提取url"""
    if not text:
        return ""
    text = re.sub(r"(https?://)", r" \1", text)  # 协议前面增加空格, 方便提取
    url = URLExtract().find_urls(text, only_unique=True)
    return url[0] if url else ""


def cookie_ellipsis(cookie: dict) -> str:
    if not cookie:
        return ""
    text = "; ".join([f"{k}={v}" for k, v in cookie.items()])
    c = min(len(text) // 3, 15)
    return f"{text[:c]}......{text[-c:]}"


def clear_params(url: str, param: str | list[str]) -> str:
    """
    删除链接指定参数
    :param url: 链接
    :param param: 参数
    :return:
    """
    params = param if isinstance(param, list) else [param]
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    for i in params.copy():
        if i in query_params:
            del query_params[i]
    new_query = "&".join([f"{k}={v[0]}" for k, v in query_params.items()])
    return parsed_url._replace(query=new_query).geturl()
