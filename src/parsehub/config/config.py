from dataclasses import dataclass
import sys
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


@dataclass
class ParseHubConfig:
    DOWNLOAD_DIR = getenv("DOWNLOAD_DIR", Path(sys.argv[0]).parent / Path("downloads/"))
    """默认下载目录"""

    douyin_api = getenv("DOUYIN_API", "https://douyin.wtf")
    """抖音解析API地址, 项目地址: https://github.com/Evil0ctal/Douyin_TikTok_Download_API"""

    provider = getenv("PROVIDER", "openai").lower()
    """模型提供商"""

    api_key = getenv("API_KEY")
    """API Key"""

    base_url = getenv("BASE_URL", "https://api.openai.com/v1")
    """API 地址"""

    model = getenv("MODEL", "gpt-4o-mini")
    """AI总结模型名称"""

    prompt = getenv("PROMPT")
    """AI总结提示词"""

    yt_dlp_duration_limit = int(getenv("YT_DLP_DURATION_LIMIT", 0))
    """使用yt-dlp下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制"""
