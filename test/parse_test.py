import asyncio
import unittest
from pathlib import Path
from typing import Any
import os
from loguru import logger

from src.parsehub.config import GlobalConfig, ParseConfig
from src.parsehub.main import ParseHub
from src.parsehub.types import ParseResult

# 测试用 URL 集合
TEST_URLS = {
    "bilibili": "https://t.bilibili.com/1169624254510006295",
    "youtube": "https://youtu.be/haAB4R5XN4I",
    "twitter": "https://x.com/aestheticspost_/status/2023047675940368400",
    "douyin": "https://v.douyin.com/example/",
    "tieba": "https://tieba.baidu.com/p/9462543824",
    "xhs": "https://www.xiaohongshu.com/discovery/item/example",
    "facebook": "https://www.facebook.com/reel/761988213517369",
    "weibo": "https://weibo.com/1234567890/example",
    "tiktok": "https://vt.tiktok.com/example/",
    "instagram": "https://www.instagram.com/p/example/",
    "weixin": "https://mp.weixin.qq.com/s/example",
    "zuiyou": "https://share.xiaochuankeji.cn/hybrid/share/post?pid=393346270",
    "coolapk": "https://www.coolapk.com/feed/70163953",
    "pipix": "https://h5.pipix.com/s/example/",
    "kuaishou": "https://v.kuaishou.com/example",
    "threads": "https://www.threads.com/@zaborona.magazine/post/DBuqMBwMfxW",
    "xiaoheihe": "https://www.xiaoheihe.cn/app/bbs/link/example",
}

# 下载保存路径
DOWNLOAD_PATH = Path(__file__).parent / "downloads"


async def progress_callback(current: int, total: int, *_: Any) -> None:
    """下载进度回调函数"""
    if total > 0:
        percentage = (current / total) * 100
        print(f"\r下载进度: {percentage:.1f}% ({current}/{total})", end="")
    else:
        print(f"\r已下载: {current} bytes", end="")


class TestParse(unittest.IsolatedAsyncioTestCase):
    """ParseHub 解析器测试类"""

    def setUp(self):
        """测试前初始化"""
        self.cookie = os.getenv("TEST_COOKIE")
        self.proxy = os.getenv("TEST_PROXY")

    def _create_parser(self, cookie: str = None, proxy: str = None) -> ParseHub:
        """创建 ParseHub 实例"""
        return ParseHub(
            ParseConfig(
                cookie=cookie or self.cookie,
                proxy=proxy or self.proxy,
            )
        )

    @logger.catch
    async def test_parse_only(self):
        """仅解析，不下载"""
        ph = self._create_parser()

        urls = [
            TEST_URLS["bilibili"],
        ]

        tasks = [ph.parse(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                raise r
            r: ParseResult
            logger.debug("解析结果: {}", r)
            logger.debug("解析结果媒体: {}", r.media)

    @logger.catch
    async def test_parse_and_download(self):
        """解析并下载"""
        ph = self._create_parser()
        GlobalConfig.duration_limit = 0

        r = await ph.parse(TEST_URLS["bilibili"])
        logger.debug("解析结果: {}", r)
        logger.debug("解析结果媒体: {}", r.media)

        s = await r.download(
            path=DOWNLOAD_PATH,
            callback=progress_callback,
        )
        logger.debug("下载结果: {}", s.media)


if __name__ == "__main__":
    unittest.main()
