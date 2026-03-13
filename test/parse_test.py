import asyncio
import os
import unittest
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.parsehub import ParseHub
from src.parsehub.config import GlobalConfig
from src.parsehub.types import ParseResult

load_dotenv()

# 测试用 URL 集合
TEST_URLS = {
    "bilibili": "https://www.bilibili.com/video/BV1R6NFzXE1H",
    "youtube": "https://www.youtube.com/watch?v=1h_uc3K4Cpg&list=RDMM1h_uc3K4Cpg&start_radio=1",
    "twitter": "https://x.com/ann_photo05/status/2030931621810254258",
    "douyin": "https://www.douyin.com/video/7615533976798727464",
    "tieba": "https://tieba.baidu.com/p/9939510114",
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


class ProgressCallback:
    async def __call__(self, current: int, total: int, unit: str, *args, **kwargs) -> None:
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
        self.cookie = os.getenv("TEST_COOKIE", None)
        self.proxy = os.getenv("TEST_PROXY", None)
        self.dy_api = os.getenv("TEST_DOUYIN_API", None)
        GlobalConfig.douyin_api = self.dy_api

    @logger.catch
    async def test_parse_only(self):
        """仅解析，不下载"""
        ph = ParseHub()

        urls = [
            TEST_URLS["tieba"],
        ]

        tasks = [ph.parse(u, cookie=self.cookie, proxy=self.proxy) for u in urls]
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
        ph = ParseHub()
        GlobalConfig.duration_limit = 0

        r = await ph.parse(TEST_URLS["bilibili"], cookie=self.cookie, proxy=self.proxy)
        logger.debug("解析结果: {}", r)
        logger.debug("解析结果媒体: {}", r.media)

        s = await r.download(
            path=DOWNLOAD_PATH,
            callback=ProgressCallback(),
        )
        logger.debug("下载结果: {}", s.media)


if __name__ == "__main__":
    unittest.main()
