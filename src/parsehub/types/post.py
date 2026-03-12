from enum import StrEnum


class PostType(StrEnum):
    """帖子类型"""

    UNKNOWN = "unknown"
    IMAGE = "image"
    VIDEO = "video"
    MULTIMEDIA = "multimedia"
    RICHTEXT = "richtext"
