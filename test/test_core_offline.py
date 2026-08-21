import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx

from parsehub import ParseHub
from parsehub.errors import ParseError, UnknownPlatform
from parsehub.parsers.base import BaseParser
from parsehub.parsers.parser.douban import DoubanParser, DoubanRichTextParseResult
from parsehub.parsers.parser.douyin import parse_video_info
from parsehub.provider_api.douban import (
    IMAGE_REFERER,
    Douban,
    DoubanError,
    DoubanPhoto,
    DoubanTopic,
    DoubanVideo,
)
from parsehub.provider_api.douyin import DouyinMobileCrawler, DouyinMobileDevice
from parsehub.types import AniRef, ImageParseResult, ImageRef, ParseResult, Platform, VideoParseResult, VideoRef
from parsehub.utils.helpers import SecretCookie, match_url, run_sync


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

    def test_run_sync_runs_coroutine_without_running_loop(self):
        async def get_value():
            return "ok"

        self.assertEqual(run_sync(get_value()), "ok")

    def test_secret_cookie_accepts_dict_input(self):
        cookie = SecretCookie({"device_id": "123", "iid": "456"})

        self.assertEqual(cookie.get_value(), {"device_id": "123", "iid": "456"})


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


class TestDouyinStorySupport(unittest.TestCase):
    def test_mobile_device_can_be_loaded_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "PARSEHUB_DOUYIN_DEVICE_ID": "1325343490970016",
                "PARSEHUB_DOUYIN_IID": "1325343490974112",
            },
            clear=True,
        ):
            device = DouyinMobileDevice.from_env()

        self.assertIsNotNone(device)
        assert device is not None
        self.assertEqual(device.device_id, "1325343490970016")
        self.assertEqual(device.iid, "1325343490974112")

    def test_mobile_device_can_be_loaded_from_register_response(self):
        device = DouyinMobileDevice.from_register_response(
            {
                "device_id": 1219790537803243,
                "install_id": 1219790537807339,
                "device_id_str": "1219790537803243",
                "install_id_str": "1219790537807339",
            },
            cdid="demo-cdid",
            openudid="demo-openudid",
        )

        self.assertIsNotNone(device)
        assert device is not None
        self.assertEqual(device.device_id, "1219790537803243")
        self.assertEqual(device.iid, "1219790537807339")
        self.assertEqual(device.cdid, "demo-cdid")
        self.assertEqual(device.openudid, "demo-openudid")

    def test_mobile_device_pool_round_robin(self):
        old_pool = DouyinMobileCrawler._device_pool
        old_index = DouyinMobileCrawler._device_pool_index
        try:
            DouyinMobileCrawler._device_pool = [
                DouyinMobileDevice(device_id="1", iid="11"),
                DouyinMobileDevice(device_id="2", iid="22"),
                DouyinMobileDevice(device_id="3", iid="33"),
            ]
            DouyinMobileCrawler._device_pool_index = 0

            picked = [DouyinMobileCrawler._next_pooled_device().device_id for _ in range(5)]

            self.assertEqual(picked, ["1", "2", "3", "1", "2"])
        finally:
            DouyinMobileCrawler._device_pool = old_pool
            DouyinMobileCrawler._device_pool_index = old_index

    def test_parse_video_info_prefers_story_default_play_url_by_data_size(self):
        video_data = {
            "duration": 9682,
            "cover": {"url_list": ["https://cdn.example/thumb.jpg"]},
            "bit_rate": [
                {
                    "bit_rate": 0,
                    "play_addr": {
                        "url_list": ["https://cdn.example/story-default.mp4"],
                        "width": 720,
                        "height": 1280,
                        "data_size": 7567631,
                    },
                },
                {
                    "bit_rate": 632,
                    "play_addr": {
                        "url_list": ["https://cdn.example/720p.mp4"],
                        "width": 720,
                        "height": 1280,
                        "data_size": 783567,
                    },
                },
            ],
        }

        info = parse_video_info(video_data)

        self.assertEqual(info["video_url"], "https://cdn.example/story-default.mp4")
        self.assertEqual(info["thumb_url"], "https://cdn.example/thumb.jpg")
        self.assertEqual(info["duration"], 9682)


class TestDoubanTopicParsing(unittest.TestCase):
    @staticmethod
    def _photo(image: dict, width: int = 500, height: int = 400) -> dict:
        return {"id": "1", "image": image, "size": {"width": width, "height": height}}

    def test_error_messages_prefer_chinese_and_contextualise_raw_codes(self):
        cases = [
            # 豆瓣给了中文提示时直接透出
            ({"localized_message": "这篇内容不存在了", "msg": "topic not found"}, "这篇内容不存在了"),
            # 只有英文错误码时补上中文上下文, 避免用户只看到 need_permission
            ({"msg": "need_permission"}, "获取话题内容失败: need_permission"),
            ({}, "获取话题内容失败: HTTP 403"),
        ]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                response = httpx.Response(403, json=payload)
                with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=response)):
                    with self.assertRaises(DoubanError) as ctx:
                        run_sync(Douban().fetch_topic_data("https://www.douban.com/group/topic/1/"))
                self.assertEqual(ctx.exception.msg, expected)

    def test_get_topic_id_accepts_both_topic_url_forms(self):
        # /group/topic/<id> 与 /topic/<id> 共用同一套 ID 与接口
        self.assertEqual(Douban.get_topic_id("https://www.douban.com/group/topic/495373106/"), "495373106")
        self.assertEqual(Douban.get_topic_id("https://www.douban.com/topic/492821052/"), "492821052")

    def test_get_topic_id_rejects_non_topic_url(self):
        for url in (
            "https://movie.douban.com/subject/1292052/",
            # 话题广场是另一套 ID, 不能被 /topic/ 规则误匹配
            "https://www.douban.com/gallery/topic/125573/",
            # 广播是另一种内容类型, 接口与数据结构均不同
            "https://m.douban.com/people/182691094/status/9372433345/",
        ):
            with self.subTest(url=url), self.assertRaises(DoubanError):
                Douban.get_topic_id(url)

    def test_photo_topic_prefers_large_and_keeps_inline_markdown(self):
        large = "https://img3.doubanio.com/view/group_topic/l/public/p1.jpg"
        small = "https://img3.doubanio.com/view/group_topic/m/public/p1.jpg"
        topic = DoubanTopic.parse(
            {
                "title": "标题",
                "content": f"<div id='content'><p>正文</p><img src=\"{large}\"/></div>",
                "photos": [
                    self._photo(
                        {
                            "is_animated": False,
                            "large": {"url": large, "width": 500, "height": 482},
                            "normal": {"url": small, "width": 200, "height": 193},
                        }
                    )
                ],
            }
        )

        self.assertEqual(topic.text_content, "正文")
        self.assertIn(large, topic.markdown_content)
        # 取 large 作正片, normal 退为缩略图
        self.assertEqual(topic.photos, [DoubanPhoto(url=large, ext="jpg", thumb_url=small, width=500, height=482)])

    def test_animated_photo_uses_mp4_variant(self):
        topic = DoubanTopic.parse(
            {
                "title": "动图",
                "content": "",
                "photos": [
                    self._photo(
                        {
                            "is_animated": True,
                            # large 是体积极大的原始 GIF, 应优先取 video
                            "large": {"url": "https://img3.doubanio.com/view/group_topic/raw/public/p2.jpg"},
                            "normal": {"url": "https://img3.doubanio.com/view/group_topic/l/public/p2.jpg"},
                            "video": {
                                "url": "https://img3.doubanio.com/view/group_topic/l/public/p2.mp4",
                                "width": 500,
                                "height": 291,
                            },
                        }
                    )
                ],
            }
        )

        self.assertEqual(
            topic.photos,
            [
                DoubanPhoto(
                    url="https://img3.doubanio.com/view/group_topic/l/public/p2.mp4",
                    ext="mp4",
                    thumb_url="https://img3.doubanio.com/view/group_topic/l/public/p2.jpg",
                    width=500,
                    height=291,
                    is_animated=True,
                )
            ],
        )

    def test_video_topic_converts_duration_to_seconds(self):
        topic = DoubanTopic.parse(
            {
                "title": "视频",
                "content": "<div id='content'><p>说明</p></div>",
                "photos": [],
                "video_info": {
                    "video_url": "https://sv1.doubanio.com/example.mp4",
                    "cover_url": "https://sv1.doubanio.com/example_cover.png",
                    "duration": "01:05",
                    "video_width": 720,
                    "video_height": 1280,
                },
            }
        )

        self.assertEqual(
            topic.video,
            DoubanVideo(
                url="https://sv1.doubanio.com/example.mp4",
                thumb_url="https://sv1.doubanio.com/example_cover.png",
                width=720,
                height=1280,
                duration=65,
            ),
        )

    def test_video_info_without_url_is_ignored(self):
        """video_info 缺 video_url 时不该当成视频话题"""
        topic = DoubanTopic.parse({"title": "t", "content": "", "photos": [], "video_info": {"duration": "00:12"}})

        self.assertEqual(topic.photos, [])


class TestDoubanParserResultTypes(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _topic(**kwargs) -> DoubanTopic:
        defaults: dict = {
            "title": "标题",
            "markdown_content": "",
            "text_content": "",
            "video": None,
            "photos": [],
        }
        return DoubanTopic(**{**defaults, **kwargs})

    @staticmethod
    async def _parse(topic: DoubanTopic):
        with patch.object(Douban, "parse", new=AsyncMock(return_value=topic)):
            return await DoubanParser()._do_parse("https://www.douban.com/group/topic/1/")

    async def test_topic_always_returns_richtext(self):
        """图 / 视频 / 纯文字 任意组合都走 RichText, 不再区分纯图"""
        photo = DoubanPhoto(url="https://img3.doubanio.com/p1.jpg", width=500, height=482)
        video = DoubanVideo(url="https://sv1.doubanio.com/a.mp4", duration=39)
        img_md = "正文\n\n![](https://img3.doubanio.com/p1.jpg)"
        cases = {
            # markdown 必须原样带过去: 图片内嵌的位置信息只存在于 markdown 里
            "图 + 正文": (self._topic(markdown_content=img_md, text_content="正文", photos=[photo]), 1, img_md),
            "纯图无正文": (self._topic(markdown_content="![](x)", photos=[photo]), 1, "![](x)"),
            "纯文字": (self._topic(markdown_content="只有文字", text_content="只有文字"), 0, "只有文字"),
            "纯视频": (self._topic(video=video), 1, ""),
        }
        for label, (topic, media_count, expected_md) in cases.items():
            with self.subTest(case=label):
                result = await self._parse(topic)
                self.assertIsInstance(result, DoubanRichTextParseResult)
                self.assertEqual(len(result.media or []), media_count)
                self.assertEqual(result.markdown_content, expected_md)

    async def test_video_with_photos_keeps_video_first(self):
        result = await self._parse(
            self._topic(
                text_content="说明",
                markdown_content="说明",
                video=DoubanVideo(url="https://sv1.doubanio.com/a.mp4", duration=39),
                photos=[DoubanPhoto(url="https://img3.doubanio.com/p1.jpg", width=500, height=482)],
            )
        )

        self.assertIsInstance(result, DoubanRichTextParseResult)
        self.assertEqual(
            result.media,
            [
                VideoRef(url="https://sv1.doubanio.com/a.mp4", duration=39),
                ImageRef(url="https://img3.doubanio.com/p1.jpg", width=500, height=482),
            ],
        )

    async def test_animated_photo_becomes_ani_ref(self):
        result = await self._parse(
            self._topic(
                photos=[
                    DoubanPhoto(
                        url="https://img3.doubanio.com/p2.mp4",
                        ext="mp4",
                        thumb_url="https://img3.doubanio.com/p2.jpg",
                        width=500,
                        height=291,
                        is_animated=True,
                    )
                ]
            )
        )

        self.assertEqual(
            result.media,
            [
                AniRef(
                    url="https://img3.doubanio.com/p2.mp4",
                    ext="mp4",
                    thumb_url="https://img3.doubanio.com/p2.jpg",
                    width=500,
                    height=291,
                )
            ],
        )

    async def test_provider_error_is_wrapped_in_parse_error(self):
        with patch.object(Douban, "parse", new=AsyncMock(side_effect=DoubanError("这篇内容不存在了"))):
            with self.assertRaisesRegex(ParseError, "豆瓣解析失败: 这篇内容不存在了"):
                await DoubanParser()._do_parse("https://www.douban.com/group/topic/1/")

    async def test_download_injects_douban_referer(self):
        result = DoubanRichTextParseResult(title="标题", media=[ImageRef(url="https://img3.doubanio.com/p1.jpg")])

        with patch.object(ParseResult, "_do_download", new=AsyncMock()) as mocked:
            await result._do_download(output_dir=Path("/tmp/does-not-matter"))

        # 豆瓣图床无 Referer 时返回 418
        self.assertEqual(mocked.await_args.kwargs["headers"]["Referer"], IMAGE_REFERER)


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
            Platform.DOUBAN: [
                "https://www.douban.com/group/topic/495373106/",
                "https://m.douban.com/group/topic/495373106/",
                "douban.com/group/topic/495373106/?_spm_id=MTU0MzM0ODY2&_i=5304694LhuE3jh",
                "https://www.douban.com/topic/492821052/?_spm_id=MTQ3NTcyNQ&dt_dapp=1",
                "https://www.douban.com/doubanapp/dispatch?uri=/group/topic/495373106/",
                "https://douc.cc/2Yx4Ol",
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
                "https://www.instagram.com/reels/DaGI8bPS3ed/",
            ],
            Platform.KUAISHOU: [
                "https://www.kuaishou.com/short-video/3xexample",
                "https://v.kuaishou.com/example",
                "https://www.kuaishou.com/f/example",
                "https://live.kuaishou.com/u/3xmdumq6gmzrr64/3xjsfb8u3d7gzyu",
                "https://v.m.chenzhongtech.com/fw/photo/3xbr5pi8hxi4e6s",
            ],
            Platform.PIPIX: [
                "https://h5.pipix.com/s/example/",
                "https://h5.pipix.com/ppx/item/1234567890",
            ],
            Platform.THREADS: [
                "https://www.threads.com/@zaborona.magazine/post/DBuqMBwMfxW",
                "https://www.threads.com/@user_name/post/DBuqMBwMfxW",
                "https://www.threads.com/share/Dq6fjYWK-/",
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
            Platform.SNAPCHAT: [
                "https://www.snapchat.com/@snapchat/spotlight/W7_EDlXWTBiXAEEniNoMPwAAYbHBpemNsYmlyAZ7mTxgqAZ7mTuxMAAAAAw",
                "https://www.snapchat.com/@creativemindsho/gBRYnSexSxSBqXdq2Y6bhAAAga2djanpnd3JlAZ8fYED8AZ8fYD7pAAAAAA",
            ],
            Platform.ZHIHU: [
                "https://www.zhihu.com/pin/2050216877939482871",
                "https://www.zhihu.com/question/2057559076813510452",
                "https://zhuanlan.zhihu.com/p/1989096494578558904",
                "https://www.zhihu.com/question/597674895/answer/3004370705",
            ],
        }

        for platform, urls in cases.items():
            for url in urls:
                with self.subTest(platform=platform.id, url=url):
                    self.assertEqual(parsehub.get_platform(url), platform)

    def test_known_unsupported_url_formats_are_not_matched(self):
        parsehub = ParseHub()
        urls = [
            "https://movie.douban.com/subject/1292052/",
            "https://book.douban.com/subject/1084336/",
            "https://www.douban.com/people/154334866/",
            "https://www.douban.com/group/657759/",
            "https://www.douban.com/gallery/topic/125573/",
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
