import contextlib
import io
import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from parsehub import cli
from parsehub.errors import ParseError


class FakeParseResult:
    def to_dict(self):
        return {
            "platform": "xhs",
            "type": "video",
            "title": "标题",
            "content": "正文",
            "raw_url": "https://example.com/post/1",
            "media": {"url": "https://cdn.example/video.mp4"},
        }


@dataclass
class FakeMediaFile:
    path: Path
    width: int = 1920
    height: int = 1080
    duration: int = 90


class FakeDownloadResult:
    def __init__(self):
        self.output_dir = Path("/tmp/parsehub-output")
        self.media = FakeMediaFile(path=Path("/tmp/parsehub-output/0.mp4"))


class FakeParseHub:
    instances = []

    def __init__(self):
        self.parse_calls = []
        self.download_calls = []
        FakeParseHub.instances.append(self)

    def parse_sync(self, url, *, proxy=None, cookie=None):
        self.parse_calls.append({"url": url, "proxy": proxy, "cookie": cookie})
        return FakeParseResult()

    def download_sync(
        self,
        url,
        path=None,
        callback=None,
        callback_args=(),
        callback_kwargs=None,
        proxy=None,
        parse_proxy=None,
        parse_cookie=None,
        save_metadata=False,
    ):
        self.download_calls.append(
            {
                "url": url,
                "path": path,
                "callback": callback,
                "callback_args": callback_args,
                "callback_kwargs": callback_kwargs,
                "proxy": proxy,
                "parse_proxy": parse_proxy,
                "parse_cookie": parse_cookie,
                "save_metadata": save_metadata,
            }
        )
        return FakeDownloadResult()

    def get_platforms(self):
        return [{"id": "xhs", "name": "小红书", "supported_types": ["视频", "图文"]}]


class ErrorParseHub:
    def parse_sync(self, url, *, proxy=None, cookie=None):
        raise ParseError("boom")


class ValueErrorParseHub:
    def parse_sync(self, url, *, proxy=None, cookie=None):
        raise ValueError("bad input")


class KeyboardInterruptParseHub:
    def parse_sync(self, url, *, proxy=None, cookie=None):
        raise KeyboardInterrupt


class TestCli(unittest.TestCase):
    def setUp(self):
        FakeParseHub.instances = []

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_parse_outputs_json_and_forwards_options(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "分享 https://example.com/post/1", "--proxy", "http://proxy", "--cookie", "a=b"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["title"], "标题")
        self.assertEqual(
            FakeParseHub.instances[0].parse_calls,
            [{"url": "分享 https://example.com/post/1", "proxy": "http://proxy", "cookie": "a=b"}],
        )

    def test_parse_compact_outputs_single_line_json(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1", "--compact"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertNotIn("\n  ", stdout)
        self.assertEqual(json.loads(stdout)["platform"], "xhs")

    def test_download_outputs_json_and_forwards_options(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(
                [
                    "download",
                    "https://example.com/post/1",
                    "-o",
                    "./out",
                    "--proxy",
                    "http://download-proxy",
                    "--parse-proxy",
                    "http://parse-proxy",
                    "--parse-cookie",
                    "token=abc",
                    "--save-metadata",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        data = json.loads(stdout)
        self.assertEqual(data["output_dir"], "/tmp/parsehub-output")
        self.assertEqual(data["media"]["path"], "/tmp/parsehub-output/0.mp4")
        self.assertEqual(
            FakeParseHub.instances[0].download_calls,
            [
                {
                    "url": "https://example.com/post/1",
                    "path": "./out",
                    "callback": None,
                    "callback_args": (),
                    "callback_kwargs": None,
                    "proxy": "http://download-proxy",
                    "parse_proxy": "http://parse-proxy",
                    "parse_cookie": "token=abc",
                    "save_metadata": True,
                }
            ],
        )

    def test_download_defaults_path_to_cwd_downloads(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["download", "https://example.com/post/1"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(FakeParseHub.instances[0].download_calls[0]["path"], Path.cwd() / "downloads")

    def test_platforms_outputs_json(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["platforms"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), [{"id": "xhs", "name": "小红书", "supported_types": ["视频", "图文"]}])

    def test_parsehub_error_returns_one(self):
        with patch.object(cli, "ParseHub", ErrorParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("boom", stderr)

    def test_value_error_returns_one(self):
        with patch.object(cli, "ParseHub", ValueErrorParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("bad input", stderr)

    def test_keyboard_interrupt_returns_130(self):
        with patch.object(cli, "ParseHub", KeyboardInterruptParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 130)
        self.assertEqual(stdout, "")
        self.assertIn("Interrupted", stderr)

    def test_argparse_error_returns_two(self):
        code, stdout, stderr = self.run_cli(["parse"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("error", stderr)


if __name__ == "__main__":
    unittest.main()
