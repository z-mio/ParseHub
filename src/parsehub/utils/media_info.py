"""媒体文件信息读取"""

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
from PIL import Image

_IMAGE_SUFFIXES = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
        ".avif",
        ".heic",
        ".ico",
    }
)

_VIDEO_SUFFIXES = frozenset(
    {
        ".mp4",
        ".mkv",
        ".webm",
        ".avi",
        ".mov",
        ".flv",
        ".ts",
        ".m4v",
        ".wmv",
        ".3gp",
    }
)


@dataclass
class MediaInfo:
    """媒体信息"""

    width: int = 0
    height: int = 0
    duration: int = 0  # 秒，图片为 0


class MediaInfoReader:
    """读取本地媒体文件的宽高和时长"""

    @staticmethod
    def read(path: str | Path) -> MediaInfo:
        """根据文件后缀自动选择读取方式"""
        suffix = Path(path).suffix.lower()
        if suffix == ".gif":
            return MediaInfoReader.read_gif(path)
        if suffix in _VIDEO_SUFFIXES:
            return MediaInfoReader.read_video(path)
        if suffix in _IMAGE_SUFFIXES:
            return MediaInfoReader.read_image(path)
        # 未知格式：先尝试图片，失败回退视频
        try:
            return MediaInfoReader.read_image(path)
        except Exception:
            try:
                return MediaInfoReader.read_video(path)
            except Exception:
                return MediaInfo()

    @staticmethod
    def read_image(path: str | Path) -> MediaInfo:
        """读取图片宽高（只解析文件头，不加载像素）"""
        with Image.open(path) as img:
            return MediaInfo(width=img.width, height=img.height)

    @staticmethod
    def read_gif(path: str | Path) -> MediaInfo:
        """读取 GIF 宽高和总时长"""
        with Image.open(path) as img:
            width, height = img.size
            total_ms = 0
            try:
                while True:
                    total_ms += img.info.get("duration", 100)
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
            return MediaInfo(width=width, height=height, duration=math.ceil(total_ms / 1000))

    @staticmethod
    def read_video(path: str | Path) -> MediaInfo:
        """读取视频宽高和时长（只读容器元数据，不解码帧）"""
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {path}")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = math.ceil(frame_count / fps) if fps > 0 else 0
            return MediaInfo(width=width, height=height, duration=duration)
        finally:
            cap.release()
