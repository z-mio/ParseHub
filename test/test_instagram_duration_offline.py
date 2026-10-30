import unittest
from unittest.mock import AsyncMock, patch

from parsehub.parsers.base.ytdlp import YtParser, YtVideoInfo
from parsehub.parsers.parser.instagram import InstagramParser
from parsehub.provider_api.instagram import InstagramAPI, InstagramMedia, InstagramMediaType, InstagramPost


class TestInstagramParserDuration(unittest.IsolatedAsyncioTestCase):
    async def test_video_prefers_provider_url_and_duration(self):
        post = InstagramPost(
            shortcode="abc",
            type=InstagramMediaType.VIDEO,
            media=[
                InstagramMedia(
                    is_video=True,
                    display_url="https://cdn.example/thumb.jpg",
                    video_url="https://cdn.example/v.mp4",
                    duration=18.018,
                    width=1920,
                    height=1080,
                )
            ],
        )
        info = YtVideoInfo(
            title="t",
            description="",
            thumbnail=None,
            url="https://www.instagram.com/p/abc/",
            info_json={},
            duration=0,
            width=1920,
            height=1080,
        )
        parser = InstagramParser()

        with (
            patch.object(InstagramParser, "_parse", AsyncMock(return_value=post)),
            patch(
                "parsehub.parsers.parser.instagram.InstagramYtParse._parse",
                AsyncMock(return_value=info),
            ),
        ):
            result = await parser._do_parse("https://www.instagram.com/reel/abc/")

        self.assertEqual(result.media.url, "https://cdn.example/v.mp4")
        self.assertEqual(result.media.duration, 18)


class TestInstagramAPIDuration(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _embed_node() -> dict:
        return {
            "__typename": "GraphVideo",
            "shortcode": "abc",
            "display_url": "https://cdn.example/thumb.jpg",
            "video_url": "https://cdn.example/v.mp4",
            "video_duration": 30.933,
            "dimensions": {"width": 1080, "height": 1920},
        }

    async def test_fills_duration_from_embed(self):
        api = InstagramAPI()
        post = InstagramPost(
            shortcode="abc",
            type=InstagramMediaType.VIDEO,
            media=[
                InstagramMedia(
                    is_video=True,
                    display_url="https://cdn.example/thumb.jpg",
                    video_url="https://cdn.example/v.mp4",
                    duration=0,
                )
            ],
        )

        with patch.object(InstagramAPI, "_fetch_embed", AsyncMock(return_value=self._embed_node())):
            result = await api._fill_missing_video_fields(object(), post, "abc")

        self.assertEqual(result.media[0].duration, 30.933)

    async def test_fills_missing_video_url_from_embed(self):
        api = InstagramAPI()
        post = InstagramPost(
            shortcode="abc",
            type=InstagramMediaType.VIDEO,
            media=[
                InstagramMedia(
                    is_video=False,
                    display_url="https://cdn.example/thumb.jpg",
                    duration=0,
                )
            ],
        )

        with patch.object(InstagramAPI, "_fetch_embed", AsyncMock(return_value=self._embed_node())):
            result = await api._fill_missing_video_fields(object(), post, "abc")

        self.assertEqual(result.media[0].video_url, "https://cdn.example/v.mp4")
        self.assertTrue(result.media[0].is_video)
        self.assertEqual(result.media[0].duration, 30.933)

    async def test_skips_embed_when_complete(self):
        api = InstagramAPI()
        post = InstagramPost(
            shortcode="abc",
            type=InstagramMediaType.VIDEO,
            media=[
                InstagramMedia(
                    is_video=True,
                    display_url="https://cdn.example/thumb.jpg",
                    video_url="https://cdn.example/v.mp4",
                    duration=18,
                )
            ],
        )

        with patch.object(InstagramAPI, "_fetch_embed", AsyncMock()) as fetch:
            await api._fill_missing_video_fields(object(), post, "abc")

        fetch.assert_not_awaited()


class _FakeYtParser(YtParser, register=False):
    async def _extract_info(self, url: str) -> dict:
        return {"title": "t", "duration": 10, "webpage_url": url}


class TestYtParserDescription(unittest.IsolatedAsyncioTestCase):
    async def test_missing_description_does_not_raise(self):
        info = await _FakeYtParser()._parse("https://example.com/v")

        self.assertEqual(info.description, "")
        self.assertEqual(info.duration, 10)
