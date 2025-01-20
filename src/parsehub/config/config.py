from abc import ABC
from dataclasses import dataclass
import sys
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class GlobalConfig(ABC):
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    proxy: str | None = None


@dataclass
class DownloadConfig(GlobalConfig):
    def __init__(
        self,
        yt_dlp_duration_limit: int = None,
        save_dir: Path | str | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
    ):
        """
        下载媒体时使用的配置
        :param yt_dlp_duration_limit: 使用yt-dlp下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制
        :param save_dir: 下载目录
        """
        if proxy:
            self.proxy = proxy

        if save_dir:
            self.save_dir = Path(save_dir)
        else:
            self.save_dir = Path(sys.argv[0]).parent / Path("downloads/")

        self.yt_dlp_duration_limit = yt_dlp_duration_limit or 0
        self.headers = headers


@dataclass
class ParseConfig(GlobalConfig):
    def __init__(self, douyin_api=None, proxy: str | None = None):
        """
        :param douyin_api: 抖音解析API地址, 项目地址: https://github.com/Evil0ctal/Douyin_TikTok_Download_API
        """
        if proxy:
            self.proxy = proxy
        self.douyin_api = douyin_api or "https://douyin.wtf"


@dataclass
class SummaryConfig(GlobalConfig):
    CN_PROMPT = """
    你是一个有用的助手，总结文章和视频字幕的要点。
    用“简体中文”总结3到8个要点，并在最后总结全部。
    """
    PROMPT = """
    You are a useful assistant to summarize the main points of articles and video captions.
    Summarize 3 to 8 points in "Simplified Chinese" and summarize them all at the end.
    """.strip()

    def __init__(
        self,
        provider=None,
        api_key=None,
        base_url=None,
        model=None,
        prompt=None,
        transcriptions_provider=None,
    ):
        """
        :param provider: 模型提供商
        :param api_key: API Key
        :param base_url: API 地址
        :param model: AI总结模型名称
        :param prompt: AI总结提示词
        :param transcriptions_provider: 语音转文本模型提供商
        """
        self.provider = provider or getenv("PROVIDER", "openai").lower()
        self.api_key = api_key or getenv("API_KEY")
        self.base_url = base_url or getenv("BASE_URL", "https://api.openai.com/v1")
        self.model = model or getenv("MODEL", "gpt-4o-mini")
        self.prompt = prompt or getenv("PROMPT", self.PROMPT)
        self.transcriptions_provider = transcriptions_provider or getenv(
            "TRANSCRIPTIONS_PROVIDER", "openai"
        )
