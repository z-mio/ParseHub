import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class _GlobalConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    ua: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    )
    default_save_dir: Path = Path(sys.argv[0]).parent / "downloads"
    """默认下载目录"""


GlobalConfig = _GlobalConfig()
