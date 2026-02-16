import json
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


class _GlobalConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    ua: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    douyin_api: HttpUrl = "https://douyin.wtf"
    duration_limit: int = 0
    """部分平台下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制"""
    default_save_dir: Path = Path(sys.argv[0]).parent / "downloads"


GlobalConfig = _GlobalConfig()


class ParseConfig(BaseModel):
    proxy: str | None = None
    cookie: dict | None = None

    @field_validator("cookie", mode="before")
    @classmethod
    def _normalize_cookie(cls, v):
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
