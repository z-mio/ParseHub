import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from parsehub.errors import ContentUnavailableError, ParseError
from parsehub.parsers.parser.bilibili import BiliMusicParseResult, BiliParse
from parsehub.provider_api.bilibili import BiliAPI
from parsehub.types import MusicFile, MusicParseResult, MusicRef, ParseResult

MUSIC_INFO = {
    "code": 0,
    "data": {
        "id": 2854883,
        "title": "残 酷 月 光",
        "cover": "http://i0.hdslb.com/bfs/music/bc477834dc9b74abdf9869989fc7a0937b25e020.jpg",
        "intro": "突然想唱 就录了一下",
        "duration": 200,
    },
}

MUSIC_PLAY = {
    "code": 0,
    "data": {"cdns": ["https://cdn.example/music-192k.m4a"], "size": 150},
}


class FakeBiliMusicAPI:
    """响应取自线上实测: song/info 正常响应、4511001 与 -400 错误响应、单条 cdn"""

    info_response: dict = MUSIC_INFO
    play_response: dict = MUSIC_PLAY
    last_sid: str | None = None

    get_music_id = staticmethod(BiliAPI.get_music_id)  # _do_parse 经 BiliAPI 路由, 替换后需保留

    def __init__(self, proxy=None):
        self.proxy = proxy

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get_music_info(self, url):
        return FakeBiliMusicAPI.info_response

    async def get_music_url(self, sid):
        FakeBiliMusicAPI.last_sid = sid
        return FakeBiliMusicAPI.play_response


class TestBiliMusicParse(unittest.IsolatedAsyncioTestCase):
    async def test_mobile_music_url_parses_to_music_result(self):
        with patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliMusicAPI):
            result = await BiliParse().parse("https://m.bilibili.com/audio/au2854883?share_source=copy")

        self.assertIsInstance(result, BiliMusicParseResult)
        self.assertIsInstance(result, MusicParseResult)
        self.assertEqual(result.to_dict()["type"], "music")
        self.assertEqual(result.title, "残 酷 月 光")
        self.assertEqual(result.content, "突然想唱 就录了一下")
        self.assertEqual(
            result.media,
            MusicRef(
                url="https://cdn.example/music-192k.m4a",
                thumb_url="http://i0.hdslb.com/bfs/music/bc477834dc9b74abdf9869989fc7a0937b25e020.jpg",
                duration=200,
            ),
        )
        self.assertEqual(result.raw_url, "https://m.bilibili.com/audio/au2854883")
        self.assertEqual(FakeBiliMusicAPI.last_sid, "2854883")

    async def test_missing_music_is_content_unavailable(self):
        with (
            patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliMusicAPI),
            patch.object(
                FakeBiliMusicAPI,
                "info_response",
                {"code": 4511001, "data": None, "message": "音乐未找到或已下架"},
            ),
        ):
            with self.assertRaises(ContentUnavailableError):
                await BiliParse()._do_parse("https://www.bilibili.com/audio/au2854883")

    async def test_api_error_keeps_server_message(self):
        with (
            patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliMusicAPI),
            patch.object(FakeBiliMusicAPI, "info_response", {"code": -400, "message": "请求错误"}),
        ):
            with self.assertRaisesRegex(ParseError, "获取音乐信息失败: 请求错误"):
                await BiliParse()._do_parse("https://www.bilibili.com/audio/au2854883")

    async def test_missing_playurl_is_parse_error(self):
        with (
            patch("parsehub.parsers.parser.bilibili.BiliAPI", FakeBiliMusicAPI),
            patch.object(
                FakeBiliMusicAPI, "play_response", {"code": 4511001, "data": None, "message": "音乐未找到或已下架"}
            ),
        ):
            with self.assertRaisesRegex(ParseError, "获取音乐链接失败"):
                await BiliParse()._do_parse("https://www.bilibili.com/audio/au2854883")


class TestMusicResultDownload(unittest.IsolatedAsyncioTestCase):
    async def test_music_result_downloads_with_m4a_and_keeps_duration(self):
        result = MusicParseResult(title="clip", music=MusicRef(url="https://cdn.example/a", duration=12))

        with patch("parsehub.types.result.download", new=AsyncMock(return_value="/tmp/clip.m4a")) as mocked:
            out = await result._do_download(output_dir=Path("/tmp/does-not-matter"))

        self.assertIsInstance(out.media, MusicFile)
        self.assertEqual(out.media.duration, 12)
        self.assertTrue(Path(mocked.await_args.args[1]).name.endswith("clip.m4a"))

    async def test_download_injects_bilibili_referer(self):
        result = BiliMusicParseResult(title="clip", music=MusicRef(url="https://cdn.example/a"))

        with patch.object(ParseResult, "_do_download", new=AsyncMock()) as mocked:
            await result._do_download(output_dir=Path("/tmp/x"))

        # 音乐 CDN 无 Referer 返回 403
        self.assertEqual(mocked.await_args.kwargs["headers"]["referer"], "https://www.bilibili.com")


if __name__ == "__main__":
    unittest.main()
