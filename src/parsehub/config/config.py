import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class _GlobalConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    default_save_dir: Path = Path(sys.argv[0]).parent / "downloads"
    """默认下载目录"""


GlobalConfig = _GlobalConfig()
