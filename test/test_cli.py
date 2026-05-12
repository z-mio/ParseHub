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
        if callback:
            import asyncio

            asyncio.run(callback(512, 1024, "bytes"))
            asyncio.run(callback(1024, 1024, "bytes"))
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

    def test_parse_defaults_to_human_readable_chinese_summary(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(
                ["parse", "分享 https://example.com/post/1", "--proxy", "http://proxy", "--cookie", "a=b"]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("平台: xhs", stdout)
        self.assertIn("标题: 标题", stdout)
        self.assertEqual(
            FakeParseHub.instances[0].parse_calls,
            [{"url": "分享 https://example.com/post/1", "proxy": "http://proxy", "cookie": "a=b"}],
        )

    def test_parse_json_outputs_json(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1", "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["title"], "标题")

    def test_parse_compact_outputs_single_line_json(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1", "--compact"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertNotIn("\n  ", stdout)
        self.assertEqual(json.loads(stdout)["platform"], "xhs")

    def test_short_parse_alias_and_default_parse(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            alias_code, alias_stdout, alias_stderr = self.run_cli(["p", "https://example.com/post/1"])
            default_code, default_stdout, default_stderr = self.run_cli(["https://example.com/post/2"])

        self.assertEqual(alias_code, 0)
        self.assertEqual(default_code, 0)
        self.assertEqual(alias_stderr, "")
        self.assertEqual(default_stderr, "")
        self.assertIn("平台: xhs", alias_stdout)
        self.assertIn("平台: xhs", default_stdout)
        self.assertEqual(FakeParseHub.instances[0].parse_calls[0]["url"], "https://example.com/post/1")
        self.assertEqual(FakeParseHub.instances[1].parse_calls[0]["url"], "https://example.com/post/2")

    def test_download_outputs_summary_progress_and_forwards_options(self):
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
                    "--metadata",
                ]
            )

        self.assertEqual(code, 0)
        self.assertIn("下载完成: /tmp/parsehub-output", stdout)
        self.assertIn("/tmp/parsehub-output/0.mp4", stdout)
        self.assertIn("解析中...", stderr)
        self.assertIn("下载中", stderr)
        call = FakeParseHub.instances[0].download_calls[0]
        self.assertEqual(call["url"], "https://example.com/post/1")
        self.assertEqual(call["path"], "./out")
        self.assertIsNotNone(call["callback"])
        self.assertEqual(call["proxy"], "http://download-proxy")
        self.assertEqual(call["parse_proxy"], "http://parse-proxy")
        self.assertEqual(call["parse_cookie"], "token=abc")
        self.assertTrue(call["save_metadata"])

    def test_short_download_alias_outputs_json_and_forwards_output_dir(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["d", "https://example.com/post/1", "--output-dir", "./out", "--json"])

        self.assertEqual(code, 0)
        self.assertIn("解析中...", stderr)
        data = json.loads(stdout)
        self.assertEqual(data["output_dir"], "/tmp/parsehub-output")
        self.assertEqual(data["media"]["path"], "/tmp/parsehub-output/0.mp4")
        self.assertEqual(FakeParseHub.instances[0].download_calls[0]["path"], "./out")

    def test_download_quiet_suppresses_feedback_and_progress_callback(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["dl", "https://example.com/post/1", "--quiet"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("下载完成: /tmp/parsehub-output", stdout)
        self.assertIsNone(FakeParseHub.instances[0].download_calls[0]["callback"])

    def test_download_no_progress_keeps_status_but_disables_callback(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["download", "https://example.com/post/1", "--no-progress"])

        self.assertEqual(code, 0)
        self.assertIn("下载完成: /tmp/parsehub-output", stdout)
        self.assertIn("解析中...", stderr)
        self.assertNotIn("下载中", stderr)
        self.assertIsNone(FakeParseHub.instances[0].download_calls[0]["callback"])

    def test_download_defaults_path_to_cwd_downloads(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["download", "https://example.com/post/1", "--quiet"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(FakeParseHub.instances[0].download_calls[0]["path"], Path.cwd() / "downloads")

    def test_platforms_outputs_aligned_human_readable_table(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["platforms"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        lines = stdout.splitlines()
        self.assertEqual(lines[0], "平台  名称    支持类型")
        self.assertEqual(lines[1], "----  ------  --------")
        self.assertEqual(lines[2], "xhs   小红书  视频、图文")

    def test_short_platforms_alias_outputs_json(self):
        with patch.object(cli, "ParseHub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["ls", "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), [{"id": "xhs", "name": "小红书", "supported_types": ["视频", "图文"]}])

    def test_parsehub_error_returns_one(self):
        with patch.object(cli, "ParseHub", ErrorParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("boom", stderr)
        self.assertIn("错误", stderr)

    def test_value_error_returns_one(self):
        with patch.object(cli, "ParseHub", ValueErrorParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("bad input", stderr)
        self.assertIn("错误", stderr)

    def test_keyboard_interrupt_returns_130(self):
        with patch.object(cli, "ParseHub", KeyboardInterruptParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 130)
        self.assertEqual(stdout, "")
        self.assertIn("已中断", stderr)

    def test_argparse_error_returns_two_in_chinese(self):
        code, stdout, stderr = self.run_cli(["parse"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("错误", stderr)


if __name__ == "__main__":
    unittest.main()
