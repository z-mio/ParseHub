import unittest
from unittest.mock import patch

from parsehub.parsers.parser.bilibili import BiliParse

VIEW = {
    "cid": 111,
    "duration": 769,
    "dimension": {"width": 1920, "height": 1080},
    "desc": "",
    "title": "test",
    "pic": "https://cdn.example/cover.jpg",
    "pages": [
        {"page": 1, "cid": 111, "duration": 190, "dimension": {"width": 1920, "height": 1080}},
        {"page": 2, "cid": 222, "duration": 193, "dimension": {"width": 1920, "height": 1080}},
    ],
}


class FakeBiliAPI:
    last_cid = None

    def __init__(self, proxy=None):
        self.proxy = proxy

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get_video_info(self, url):
        return {"data": {"View": VIEW}}

    async def get_buvid(self):
        return "b3", "b4"

    async def get_video_playurl(self, url, cid, b3, b4):
        FakeBiliAPI.last_cid = cid
        return {"data": {"durl": [{"url": "https://cdn.example/video.mp4"}]}}


class TestBilibiliParts(unittest.IsolatedAsyncioTestCase):
    async def test_default_part_uses_first_page_duration(self):
        with patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliAPI):
            result = await BiliParse().bili_api_parse("https://www.bilibili.com/video/BV1zLap6VEz1/")

        self.assertEqual(result.media.duration, 190)
        self.assertEqual(FakeBiliAPI.last_cid, 111)

    async def test_requested_part_uses_page_duration(self):
        with patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliAPI):
            result = await BiliParse().bili_api_parse("https://www.bilibili.com/video/BV1zLap6VEz1/?p=2")

        self.assertEqual(result.media.duration, 193)
        self.assertEqual(FakeBiliAPI.last_cid, 222)

    async def test_out_of_range_falls_back_to_default_part(self):
        with patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliAPI):
            result = await BiliParse().bili_api_parse("https://www.bilibili.com/video/BV1zLap6VEz1/?p=99")

        self.assertEqual(result.media.duration, 190)
        self.assertEqual(FakeBiliAPI.last_cid, 111)
