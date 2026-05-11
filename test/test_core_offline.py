import unittest
from urllib.parse import parse_qs, urlparse

from src.parsehub import ParseHub
from src.parsehub.parsers.base import BaseParser
from src.parsehub.types import ImageParseResult, ImageRef, Platform, VideoParseResult, VideoRef
from src.parsehub.utils.utils import match_url, normalize_cookie, run_sync


class DummyParser(BaseParser, register=False):
    __platform__ = Platform.TIEBA
    __supported_type__ = ["测试"]
    __match__ = r"^(https?://)?dummy\.com/items/\d+"
    __reserved_parameters__ = ["keep"]
    __after_clean_parameters__ = ["token"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen_raw_url = None

    async def _do_parse(self, raw_url: str) -> VideoParseResult:
        self.seen_raw_url = raw_url
        return VideoParseResult(title=" Dummy title ", content=" Dummy content ", video="https://cdn.example/video.mp4")


class TestCoreUtilities(unittest.TestCase):
    def test_match_url_extracts_first_url_from_shared_text(self):
        text = "复制文案 https://example.com/posts/1?foo=bar 后面还有 https://example.org/ignored"

        self.assertEqual(match_url(text), "https://example.com/posts/1?foo=bar")

    def test_match_url_returns_empty_string_without_url(self):
        self.assertEqual(match_url(""), "")
        self.assertEqual(match_url("plain text without a link"), "")

    def test_match_url_splits_adjacent_http_urls(self):
        text = "https://example.com/firsthttps://example.org/second"

        self.assertEqual(match_url(text), "https://example.com/first")

    def test_normalize_cookie_preserves_none_and_dict_values(self):
        cookie = {"session": "abc", "flag": ""}

        self.assertIsNone(normalize_cookie(None))
        self.assertIs(normalize_cookie(cookie), cookie)

    def test_normalize_cookie_parses_cookie_header_strings(self):
        cookie = normalize_cookie("Cookie: session = abc ; theme= light ; secure")

        self.assertEqual(cookie, {"session": "abc", "theme": "light", "secure": ""})

    def test_normalize_cookie_parses_json_object_strings(self):
        cookie = normalize_cookie('{"session": " abc ", "empty": null, "number": 123}')

        self.assertEqual(cookie, {"session": "abc", "empty": "", "number": "123"})

    def test_normalize_cookie_returns_none_for_blank_strings(self):
        self.assertIsNone(normalize_cookie("  \t  "))

    def test_normalize_cookie_rejects_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "cookie JSON解析失败"):
            normalize_cookie('{"session": }')
        with self.assertRaisesRegex(ValueError, "cookie 必须是字符串、字典、JSON 或 None"):
            normalize_cookie(123)

    def test_run_sync_runs_coroutine_without_running_loop(self):
        async def get_value():
            return "ok"

        self.assertEqual(run_sync(get_value()), "ok")


class TestBaseParserUrlCleaning(unittest.IsolatedAsyncioTestCase):
    async def test_get_raw_url_keeps_reserved_and_parse_only_parameters(self):
        parser = DummyParser()

        raw_url = await parser.get_raw_url(
            "分享 https://dummy.com/items/42?drop=1&keep=stay&token=parse-token", clean_all=False
        )

        self.assertEqual(urlparse(raw_url).scheme, "https")
        self.assertEqual(urlparse(raw_url).netloc, "dummy.com")
        self.assertEqual(urlparse(raw_url).path, "/items/42")
        self.assertEqual(parse_qs(urlparse(raw_url).query), {"keep": ["stay"], "token": ["parse-token"]})

    async def test_get_raw_url_removes_parse_only_parameters_when_clean_all(self):
        parser = DummyParser()

        raw_url = await parser.get_raw_url(
            "https://dummy.com/items/42?drop=1&keep=stay&token=parse-token", clean_all=True
        )

        self.assertEqual(raw_url, "https://dummy.com/items/42?keep=stay")

    async def test_parse_removes_after_clean_parameters_from_result_raw_url(self):
        parser = DummyParser()

        result = await parser.parse("https://dummy.com/items/42?drop=1&keep=stay&token=parse-token")

        self.assertEqual(parser.seen_raw_url, "https://dummy.com/items/42?keep=stay&token=parse-token")
        self.assertEqual(result.platform, Platform.TIEBA)
        self.assertEqual(result.raw_url, "https://dummy.com/items/42?keep=stay")


class TestParserRegistry(unittest.TestCase):
    def test_parsehub_reports_platform_metadata_without_network_calls(self):
        parsehub = ParseHub()

        platforms = parsehub.get_platforms()
        by_id = {platform["id"]: platform for platform in platforms}

        self.assertEqual(len(by_id), len(platforms))
        self.assertEqual(by_id["tieba"]["name"], Platform.TIEBA.display_name)
        self.assertIn("图文", by_id["tieba"]["supported_types"])
        self.assertEqual(parsehub.get_platform("https://tieba.baidu.com/p/9939510114"), Platform.TIEBA)
        self.assertIsNone(parsehub.get_platform("https://example.invalid/not-supported"))


class TestParseResultToDict(unittest.TestCase):
    def test_video_parse_result_to_dict_serializes_platform_type_and_single_media(self):
        result = VideoParseResult(
            title="  Video title  ",
            content="  Video body  ",
            video=VideoRef(
                url="https://cdn.example/video.mp4",
                thumb_url="https://cdn.example/thumb.jpg",
                width=1920,
                height=1080,
                duration=90,
            ),
        )
        result.platform = Platform.BILIBILI
        result.raw_url = "https://www.bilibili.com/video/BV123"

        self.assertEqual(
            result.to_dict(),
            {
                "platform": "bilibili",
                "type": "video",
                "title": "Video title",
                "content": "Video body",
                "raw_url": "https://www.bilibili.com/video/BV123",
                "media": {
                    "url": "https://cdn.example/video.mp4",
                    "ext": "mp4",
                    "thumb_url": "https://cdn.example/thumb.jpg",
                    "width": 1920,
                    "height": 1080,
                    "duration": 90,
                },
            },
        )

    def test_image_parse_result_to_dict_serializes_media_lists(self):
        result = ImageParseResult(
            title="Images",
            content="Body",
            photo=[ImageRef(url="https://cdn.example/one.jpg", width=100), ImageRef(url="https://cdn.example/two.jpg")],
        )

        self.assertEqual(
            result.to_dict()["media"],
            [
                {
                    "url": "https://cdn.example/one.jpg",
                    "ext": "jpg",
                    "thumb_url": None,
                    "width": 100,
                    "height": 0,
                },
                {
                    "url": "https://cdn.example/two.jpg",
                    "ext": "jpg",
                    "thumb_url": None,
                    "width": 0,
                    "height": 0,
                },
            ],
        )


class TestRunSyncInsideEventLoop(unittest.IsolatedAsyncioTestCase):
    async def test_run_sync_raises_inside_existing_event_loop(self):
        async def get_value():
            return "ok"

        with self.assertRaisesRegex(RuntimeError, "sync API cannot be called from a running event loop"):
            run_sync(get_value())


if __name__ == "__main__":
    unittest.main()
