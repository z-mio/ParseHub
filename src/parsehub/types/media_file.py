from dataclasses import dataclass
from pathlib import Path

from src.parsehub.utils.media_info import MediaInfoReader


@dataclass(kw_only=True)
class MediaFile:
    """本地媒体
    Attributes:
        path: 路径
        width: 宽度
        height: 高度
    """

    path: str | Path
    width: int = 0
    height: int = 0

    def __post_init__(self):
        if not self.width:
            info = MediaInfoReader.read(path=self.path)
            self.width = info.width
            self.height = info.height


@dataclass(kw_only=True)
class VideoFile(MediaFile):
    """本地视频
    Attributes:
        path: 路径
        width: 宽度
        height: 高度
        duration: 视频时长，单位: 秒
    """

    duration: int = 0

    def __post_init__(self):
        if not self.width or not self.duration:
            info = MediaInfoReader.read(path=self.path)
            self.width = info.width
            self.height = info.height
            self.duration = info.duration


@dataclass(kw_only=True)
class ImageFile(MediaFile):
    """本地图片
    Attributes:
        path: 路径
        width: 宽度
        height: 高度
    """


@dataclass(kw_only=True)
class AniFile(MediaFile):
    """本地动图
    Attributes:
        path: 路径
        width: 宽度
        height: 高度
        duration: 视频时长，单位: 秒
    """

    duration: int = 0

    def __post_init__(self):
        if not self.width or not self.duration:
            info = MediaInfoReader.read(path=self.path)
            self.width = info.width
            self.height = info.height
            self.duration = info.duration


@dataclass(kw_only=True)
class LivePhotoFile(MediaFile):
    """本地 Live Photo
    Attributes:
        path: 图片路径
        width: 宽度
        height: 高度
        video_path: 视频路径
        duration: 视频时长，单位: 秒
    """

    video_path: str | Path
    duration: int = 3

    def __post_init__(self):
        if not self.width or not self.duration:
            info = MediaInfoReader.read(path=self.video_path)
            self.width = info.width
            self.height = info.height
            self.duration = info.duration


AnyMediaFile = MediaFile | VideoFile | ImageFile | AniFile | LivePhotoFile

__all__ = ["MediaFile", "VideoFile", "ImageFile", "AniFile", "LivePhotoFile", "AnyMediaFile"]
