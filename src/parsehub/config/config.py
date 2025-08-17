from abc import ABC
import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from dotenv import load_dotenv

load_dotenv()


class GlobalConfig(ABC):
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


class DownloadConfig(GlobalConfig, BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    yt_dlp_duration_limit: int = Field(
        default=0,
        ge=0,
    )
    """使用yt-dlp下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制"""

    save_dir: Path = Field(default=Path(sys.argv[0]).parent / "downloads")
    headers: dict | None = Field(default=None, validation_alias="DOWNLOADER_HEADERS")
    proxy: str | None = Field(default=None, validation_alias="DOWNLOADER_PROXY")


class ParseConfig(GlobalConfig, BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    douyin_api: str | None = Field(default="https://douyin.wtf")
    proxy: str | None = Field(default=None, validation_alias="PARSER_PROXY")


class SummaryConfig(GlobalConfig, BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    provider: str | None = "openai"
    api_key: str | None = None
    base_url: str | None = "https://api.openai.com/v1"
    model: str | None = "gpt-5-nano"
    prompt: str = """
        You are a useful assistant to summarize the main points of articles and video captions.
        Summarize 3 to 8 points in "Simplified Chinese" and put the summary at the beginning.
        """.strip()
    """你是一个有用的助手，总结文章和视频字幕的要点。用“简体中文”总结3到8个要点，并在开头总结全部。"""
    transcriptions_provider: str | None = None
    transcriptions_api_key: str | None = None
    transcriptions_base_url: str | None = None
    