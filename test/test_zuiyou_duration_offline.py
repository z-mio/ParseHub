import unittest
from unittest.mock import AsyncMock, patch

from parsehub.parsers.parser.zuiyou import ZuiYouParser
from parsehub.provider_api.zuiyou import Media, MediaType, ZuiYou, ZuiYouPost


class TestZuiyouDuration(unittest.TestCase):
    def test_parse_reads_video_dur(self):
        payload = {
            "data": {
                "post": {
                    "content": "x",
                    "imgs": [
                        {
                            "id": 1,
                            "urls": {"a": {"urls": ["https://cdn.example/thumb.jpg"]}},
                            "video": True,
                        }
                    ],
                    "videos": {"1": {"dur": 5, "url": "https://cdn.example/v.mp4"}},
                }
            }
        }

        post = ZuiYouPost.parse(payload)

        self.assertEqual(post.media[0].type, MediaType.VIDEO)
        self.assertEqual(post.media[0].duration, 5)
        self.assertEqual(post.media[0].url, "https://cdn.example/v.mp4")

    def test_photo_duration_defaults_to_zero(self):
        payload = {
            "data": {
                "post": {
                    "imgs": [
                        {
                            "id": 1,
                            "urls": {"a": {"urls": ["https://cdn.example/p.jpg"]}},
                        }
                    ]
                }
            }
        }

        post = ZuiYouPost.parse(payload)

        self.assertEqual(post.media[0].duration, 0)


class TestZuiyouParserDuration(unittest.IsolatedAsyncioTestCase):
    async def test_parser_sets_video_duration(self):
        zy = ZuiYouPost(
            content="x",
            media=[
                Media(
                    url="https://cdn.example/v.mp4",
                    thumb_url="https://cdn.example/thumb.jpg",
                    type=MediaType.VIDEO,
                    duration=19,
                )
            ],
            raw={},
        )

        with patch.object(ZuiYou, "parse", AsyncMock(return_value=zy)):
            result = await ZuiYouParser()._do_parse("https://s.izuiyou.com/s/abc")

        self.assertEqual(result.media[0].duration, 19)
