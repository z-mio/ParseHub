import unittest
from urllib.parse import parse_qs, urlparse

from parsehub import ParseHub
from parsehub.errors import ParseError, UnknownPlatform
from parsehub.parsers.base import BaseParser
from parsehub.types import ImageParseResult, ImageRef, Platform, VideoParseResult, VideoRef
from parsehub.utils.utils import match_url, normalize_cookie, run_sync


class DummyParser(BaseParser):
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


class BrokenParser(BaseParser):
    __platform__ = Platform.XHS
    __supported_type__ = ["测试"]
    __match__ = r"^(https?://)?broken\.example\.com/items/\d+"

    async def _do_parse(self, raw_url: str) -> VideoParseResult:
        raise ValueError("provider exploded")


class ParseErrorParser(BaseParser):
    __platform__ = Platform.XHS
    __supported_type__ = ["测试"]
    __match__ = r"^(https?://)?parse-error\.example\.com/items/\d+"

    async def _do_parse(self, raw_url: str) -> VideoParseResult:
        raise ParseError("already normalized")


for _parser in (DummyParser, BrokenParser, ParseErrorParser):
    if _parser in BaseParser._registry:
        BaseParser._registry.remove(_parser)


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


class TestParseHubExceptionBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_parse_wraps_unexpected_parser_errors_as_parse_error(self):
        parsehub = ParseHub()
        parsehub.parsers = [BrokenParser]

        with self.assertRaisesRegex(ParseError, "provider exploded"):
            await parsehub.parse("https://broken.example.com/items/1")

    async def test_parse_preserves_existing_parse_error(self):
        parsehub = ParseHub()
        parsehub.parsers = [ParseErrorParser]

        with self.assertRaisesRegex(ParseError, "already normalized"):
            await parsehub.parse("https://parse-error.example.com/items/1")

    async def test_parse_preserves_unknown_platform(self):
        parsehub = ParseHub()
        parsehub.parsers = []

        with self.assertRaisesRegex(UnknownPlatform, "example.invalid"):
            await parsehub.parse("https://example.invalid/not-supported")


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


class TestPlatformUrlMatching(unittest.TestCase):
    def test_supported_platform_url_formats(self):
        parsehub = ParseHub()
        cases = {
            Platform.BILIBILI: [
                "BV1R6NFzXE1H",
                "https://www.bilibili.com/video/BV1R6NFzXE1H",
                "https://m.bilibili.com/video/BV1R6NFzXE1H?p=2",
                "https://www.bilibili.com/video/av123456",
                "https://www.bilibili.com/opus/1234567890123456789",
                "https://t.bilibili.com/1234567890123456789",
                "https://b23.tv/abc123",
                "https://bili2233.cn/abc123",
            ],
            Platform.COOLAPK: [
                "https://www.coolapk.com/feed/70163953",
                "https://www.coolapk.com/picture/123456",
            ],
            Platform.DOUYIN: [
                "https://www.douyin.com/video/7615533976798727464",
                "https://www.douyin.com/note/7615533976798727464",
                "https://v.douyin.com/iABC123/",
                "https://iesdouyin.com/share/video/7615533976798727464/",
            ],
            Platform.FACEBOOK: [
                "https://www.facebook.com/watch?v=761988213517369",
                "https://www.facebook.com/share/v/761988213517369/",
                "https://www.facebook.com/share/r/761988213517369/",
                "https://www.facebook.com/example/videos/761988213517369/",
                "https://www.facebook.com/reel/761988213517369",
            ],
            Platform.INSTAGRAM: [
                "https://www.instagram.com/p/C0example/",
                "https://instagram.com/reel/C0example/",
                "https://www.instagram.com/share/BAexample/",
                "https://www.instagram.com/user.name/p/C0example/",
                "https://www.instagram.com/user.name/reel/C0example/",
            ],
            Platform.KUAISHOU: [
                "https://www.kuaishou.com/short-video/3xexample",
                "https://v.kuaishou.com/example",
                "https://www.kuaishou.com/f/example",
                "https://live.kuaishou.com/u/3xmdumq6gmzrr64/3xjsfb8u3d7gzyu",
            ],
            Platform.PIPIX: [
                "https://h5.pipix.com/s/example/",
                "https://h5.pipix.com/ppx/item/1234567890",
            ],
            Platform.THREADS: [
                "https://www.threads.com/@zaborona.magazine/post/DBuqMBwMfxW",
                "https://www.threads.com/@user_name/post/DBuqMBwMfxW",
            ],
            Platform.TIEBA: [
                "https://tieba.baidu.com/p/9939510114",
                "https://tieba.baidu.com/p/9939510114?pn=2",
            ],
            Platform.TIKTOK: [
                "https://www.tiktok.com/@scout2015/video/6718335390845095173",
                "https://www.tiktok.com/@scout2015/photo/6718335390845095173",
                "https://vt.tiktok.com/ZSexample/",
                "https://vm.tiktok.com/ZSexample/",
            ],
            Platform.TWITTER: [
                "https://x.com/ann_photo05/status/2030931621810254258",
                "https://twitter.com/ann_photo05/status/2030931621810254258",
                "https://mobile.twitter.com/ann_photo05/status/2030931621810254258",
                "https://fixupx.com/ann_photo05/status/2030931621810254258",
            ],
            Platform.WEIBO: [
                "https://weibo.com/1234567890/Nexample",
                "https://weibo.com/detail/1234567890123456",
                "https://m.weibo.cn/status/Nexample",
                "https://video.weibo.com/show?fid=1034:5307969483767845",
                "https://weibo.com/tv/show/1034:5307969483767845",
            ],
            Platform.WEIXIN: [
                "https://mp.weixin.qq.com/s/example",
                "https://mp.weixin.qq.com/s/example?__biz=MzA&mid=123",
            ],
            Platform.XHS: [
                "https://www.xiaohongshu.com/explore/6a01c2fc0000000037036508",
                "https://www.xiaohongshu.com/discovery/item/6a01c2fc0000000037036508",
                "https://xhslink.com/a/example",
            ],
            Platform.XIAOHEIHE: [
                "https://www.xiaoheihe.cn/app/bbs/link/174972336",
                "https://www.xiaoheihe.cn/v3/bbs/app/api/web/share?link_id=174972336",
                "https://api.xiaoheihe.cn/v3/bbs/app/link?link_id=174972336",
            ],
            Platform.YOUTUBE: [
                "https://www.youtube.com/watch?v=1h_uc3K4Cpg",
                "https://www.youtube.com/shorts/1h_uc3K4Cpg",
                "https://youtu.be/1h_uc3K4Cpg",
                "https://m.youtube.com/watch?v=1h_uc3K4Cpg",
                "https://music.youtube.com/watch?v=1h_uc3K4Cpg&list=RDMM1h_uc3K4Cpg",
            ],
            Platform.ZUIYOU: [
                "https://share.xiaochuankeji.cn/hybrid/share/post?pid=393346270",
                "https://share.xiaochuankeji.cn/hybrid/share/post?pid=393346270&zy_to=applink",
            ],
        }

        for platform, urls in cases.items():
            for url in urls:
                with self.subTest(platform=platform.id, url=url):
                    self.assertEqual(parsehub.get_platform(url), platform)

    def test_known_unsupported_url_formats_are_not_matched(self):
        parsehub = ParseHub()
        urls = [
            "https://www.douyin.com/share/user/MS4wLjABAAAA",
            "https://www.douyin.com/qishui/share/video/123456",
            "https://www.tiktok.com/share/user/123456",
            "https://www.tiktok.com/qishui/share/video/123456",
            "https://weibo.com/u/1234567890",
            "https://www.youtube.com/live/1h_uc3K4Cpg",
            "https://www.youtube.com/post/Ugkxexample",
            "https://www.youtube.com/@example",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertIsNone(parsehub.get_platform(url))


class TestRunSyncInsideEventLoop(unittest.IsolatedAsyncioTestCase):
    async def test_run_sync_raises_inside_existing_event_loop(self):
        async def get_value():
            return "ok"

        with self.assertRaisesRegex(RuntimeError, "sync API cannot be called from a running event loop"):
            run_sync(get_value())


if __name__ == "__main__":
    unittest.main()
