from typing import Literal, Protocol

ProgressUnit = Literal["bytes", "count"]


class ProgressCallback(Protocol):
    """下载进度回调: (current, total, unit, *args) -> None"""

    async def __call__(self, current: int, total: int, unit: ProgressUnit, *args) -> None:
        """
        下载进度回调
        Args:
            current: 当前进度值
            total: 总进度值
            unit: 进度单位
                - ``bytes``: 字节进度，用于单文件下载时报告已下载/总字节数
                - ``count``: 计数进度，用于多文件下载时报告已完成/总文件数
            *args: 自定义参数

        Returns:
            None
        """


__all__ = ["ProgressCallback", "ProgressUnit"]
