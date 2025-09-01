import asyncio
import unittest
from typing import Any

from loguru import logger

from src.parsehub.config import ParseConfig
from src.parsehub.main import ParseHub

TEST_URLS = {
    "bilibili": "https://b23.tv/635jNDs",
    "youtube": "https://www.youtube.com/watch?v=1iZC69TAcfc",
    "twitter": "https://twitter.com/SR_Malaya/status/1951863360968106037",
    "douyin": "www.douyin.com/video/7542384144538504448",
    "tieba": "https://tieba.baidu.com/p/9861214687",
    "xhs": "http://xhslink.com/n/3BAwyUCnCcY",
    "facebook": "https://www.facebook.com/share/r/1FpXSkzHwe/",
    "weibo": "https://weibo.com/2539961154/5202138202374690",
    "tiktok": "https://www.tiktok.com/t/ZP8hE66xw/",
    "instagram": "https://www.instagram.com/reel/DNtql3eZkTa",
    "weixin": "https://mp.weixin.qq.com/s/7qseHCqY0bHk4_cgIcPe5g",
    "zuiyou": "https://share.xiaochuankeji.cn/hybrid/share/post?pid=393346270",
    "coolapk": "https://www.coolapk.com/feed/66827836?s=MmZjM2Q1YjUzY2NhNjFnNjhhYmQyODd6a1551b1",
    "pipix": "https://h5.pipix.com/s/t4kb2cV7BB0/",
}


class TestParse(unittest.IsolatedAsyncioTestCase):
    @logger.catch
    async def test_parse_only(self):
        """仅解析，不下载。"""
        cookie = ""
        ph = ParseHub(
            ParseConfig(
                cookie=cookie,
                # proxy="http://127.0.0.1:7890",
            )
        )

        urls = [
            TEST_URLS["xhs"],
        ]

        tasks = [ph.parse(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                raise r
            logger.debug("解析结果: {}", r.media)

    @logger.catch
    async def test_parse_and_download(self):
        """解析并下载。"""
        cookie = ""
        ph = ParseHub(ParseConfig(cookie=cookie))

        r = await ph.parse(TEST_URLS["xhs"])

        s = await r.download(
            callback=progress_callback,
            # config=DownloadConfig(proxy="http://127.0.0.1:7890"),
        )
        logger.debug("下载结果: {}", s.media)

    @logger.catch
    async def test_concurrent_gather_parse(self):
        """使用 asyncio.gather 并发解析多个链接（不下载）。"""
        cookie = ""
        ph = ParseHub(ParseConfig(cookie=cookie))

        urls = [
            TEST_URLS["youtube"],
            TEST_URLS["bilibili"],
            TEST_URLS["pipix"],
        ]

        tasks = [ph.parse(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                raise r
            logger.debug("并发解析结果: {}", r.media)


async def progress_callback(current: int, total: int, *_: Any) -> None:
    if total > 0:
        percentage = (current / total) * 100
        print(f"\r下载进度: {percentage:.1f}% ({current}/{total})", end="")
    else:
        print(f"\r已下载: {current} bytes", end="")
