from pathlib import Path
import sys
from typing import Dict, Optional


class SubmoduleManager:
    def __init__(self):
        self.deps_dir = Path(__file__).parent
        self.path_mappings: Dict[str, Path] = {}

    def add_submodule(
        self, name: str, relative_path: str, source_dir: Optional[str] = None
    ):
        """添加子模块路径映射"""
        submodule_path = self.deps_dir / relative_path
        self.path_mappings[name] = submodule_path

        # 添加主模块路径
        if str(submodule_path) not in sys.path:
            sys.path.insert(0, str(submodule_path))

        # 添加源码目录路径（如果指定）
        if source_dir:
            source_path = submodule_path / source_dir
            if str(source_path) not in sys.path:
                sys.path.insert(0, str(source_path))

    def setup_all(self):
        """设置所有子模块的路径"""
        # 添加所有需要的子模块
        self.add_submodule("xhs", "xhs", "xhs")
