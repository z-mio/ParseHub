from enum import Enum


class Platform(Enum):
    """支持的平台"""

    BILIBILI = ("bilibili", "Bilibili")
    COOLAPK = ("coolapk", "酷安")
    DOUYIN = ("douyin", "抖音|TikTok")
    FACEBOOK = ("facebook", "Facebook")
    INSTAGRAM = ("instagram", "Instagram")
    KUAISHOU = ("kuaishou", "快手")
    PIPIX = ("pipix", "皮皮虾")
    THREADS = ("threads", "Threads")
    TIEBA = ("tieba", "贴吧")
    TWITTER = ("twitter", "Twitter")
    WEIBO = ("weibo", "微博")
    WEIXIN = ("weixin", "微信公众号")
    XHS = ("xhs", "小红书")
    XIAOHEIHE = ("xiaoheihe", "小黑盒")
    YOUTUBE = ("youtube", "Youtube")
    ZUIYOU = ("zuiyou", "最右")

    def __init__(self, platform_id: str, platform_name: str):
        self.id = platform_id
        self.display_name = platform_name

    def __str__(self):
        return self.display_name
