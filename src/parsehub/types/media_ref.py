from dataclasses import dataclass


@dataclass(kw_only=True)
class MediaRef:
    """媒体
    Attributes:
        url: URL
        ext: 默认扩展名
        thumb_url: 缩略图 URL
        width: 宽度
        height: 高度
    """

    url: str = None
    ext: str = None
    thumb_url: str = None
    width: int = 0
    height: int = 0


@dataclass(kw_only=True)
class VideoRef(MediaRef):
    """视频
    Attributes:
        url: URL
        ext: 默认扩展名
        thumb_url: 缩略图 URL
        width: 宽度
        height: 高度
        duration: 视频时长，单位: 秒
    """

    ext: str = "mp4"
    duration: int = 0


@dataclass(kw_only=True)
class ImageRef(MediaRef):
    """图片
    Attributes:
        url: URL
        ext: 默认扩展名
        thumb_url: 缩略图 URL
        width: 宽度
        height: 高度
    """

    ext: str = "jpg"

    def __post_init__(self):
        if self.thumb_url is None:
            self.thumb_url = self.url


@dataclass(kw_only=True)
class AniRef(MediaRef):
    """动图
    Attributes:
        url: URL
        ext: 默认扩展名
        width: 宽度
        height: 高度
        duration: 视频时长，单位: 秒
    """

    ext: str = "gif"
    duration: int = 0


@dataclass(kw_only=True)
class LivePhotoRef(MediaRef):
    """Live Photo
    Attributes:
        url: URL
        ext: 默认扩展名
        thumb_url: 缩略图 URL
        width: 宽度
        height: 高度
        video_url: 视频链接
        video_ext: 视频默认扩展名
        duration: 视频时长，单位: 秒
    """

    ext: str = "jpg"
    video_url: str = None
    video_ext: str = "mp4"
    duration: int = 3

    def __post_init__(self):
        if self.thumb_url is None:
            self.thumb_url = self.url


AnyMediaRef = ImageRef | VideoRef | AniRef | LivePhotoRef

__all__ = ["MediaRef", "VideoRef", "ImageRef", "AniRef", "LivePhotoRef", "AnyMediaRef"]
