import json
import os
import shutil
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()
TEMP_DIR = Path("./temp")
if TEMP_DIR.exists():
    shutil.rmtree(str(TEMP_DIR), ignore_errors=True)
TEMP_DIR.mkdir(exist_ok=True)


class GlobalConfig:
    ua: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    douyin_api: str = "https://douyin.wtf"
    duration_limit: int = 0
    """部分平台下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制"""


class DownloadConfig(BaseModel):
    save_dir: Path = Field(default=Path(sys.argv[0]).parent / "downloads")
    headers: dict | None = Field(default=None)
    proxy: str | None = Field(default=os.getenv("DOWNLOADER_PROXY"))


class ParseConfig(BaseModel):
    proxy: str | None = Field(default=os.getenv("PARSER_PROXY"))
    cookie: dict | None = Field(default=None)

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

        raise ValueError("cookie 必须是字符串、字典或 None")


class SummaryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    provider: Literal["openai"] = "openai"
    api_key: str | None = None
    base_url: str | None = "https://api.openai.com/v1"
    model: str | None = "gpt-5-nano"
    prompt: str = """
        Use "Simplified Chinese" to summarize the key points of articles and video subtitles.
        Summarize it in one sentence at the beginning and then write out n key points.
        """.strip()
    """使用"简体中文"总结文章和视频字幕的要点。在开头进行一句话总结, 然后写出n个要点。"""
    transcriptions_provider: Literal["openai", "fast_whisper", "azure"] = "openai"
    transcriptions_api_key: str | None = None
    transcriptions_base_url: str | None = None
