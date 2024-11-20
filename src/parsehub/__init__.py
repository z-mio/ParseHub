from .deps.submodule_manager import SubmoduleManager
from .main import ParseHub

manager = SubmoduleManager()
manager.setup_all()

__all__ = ["ParseHub"]
