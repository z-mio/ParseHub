import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, HttpUrl


class _GlobalConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    ua: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    )
    douyin_api: HttpUrl = "https://douyin.wtf/"
    """建议自行部署: https://github.com/Evil0ctal/Douyin_TikTok_Download_API"""
    duration_limit: int = 0
    """部分平台下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制"""
    default_save_dir: Path = Path(sys.argv[0]).parent / "downloads"


GlobalConfig = _GlobalConfig()
