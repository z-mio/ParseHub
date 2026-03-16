import asyncio
import json
import re

from urlextract import URLExtract


def get_event_loop():
    try:
        event_loop = asyncio.get_running_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
    return event_loop


_url_extractor = URLExtract()


def match_url(text: str) -> str:
    """从文本中提取url"""
    if not text:
        return ""
    text = re.sub(r"(https?://)", r" \1", text)  # 协议前面增加空格, 方便提取
    url = _url_extractor.find_urls(text, only_unique=True)
    return url[0] if url else ""


def cookie_ellipsis(cookie: dict) -> str:
    if not cookie:
        return ""
    text = "; ".join([f"{k}={v}" for k, v in cookie.items()])
    c = min(len(text) // 3, 15)
    return f"{text[:c]}......{text[-c:]}"


def normalize_cookie(v):
    if v is None or isinstance(v, dict):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None

        if s.startswith("{") and s.endswith("}"):
            try:
                data = json.loads(s)
            except Exception as e:
                raise ValueError(f"cookie JSON解析失败: {e}") from e
            if not isinstance(data, dict):
                raise ValueError("cookie JSON必须是对象类型")
            return {str(k).strip(): "" if v is None else str(v).strip() for k, v in data.items()}

        if s.lower().startswith("cookie:"):
            s = s[7:].strip()

        parts = [p.strip() for p in s.split(";") if p.strip()]
        result: dict[str, str] = {}
        for p in parts:
            if "=" not in p:
                key = p.strip()
                if key:
                    result[key] = ""
                continue
            k, val = p.split("=", 1)
            result[k.strip()] = val.strip()
        return result or None

    raise ValueError("cookie 必须是字符串、字典、JSON 或 None")
