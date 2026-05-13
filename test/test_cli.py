import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

from src.parsehub import cli
from src.parsehub.cli_config import ConfigStore, FileCookieStore
from src.parsehub.errors import ParseError


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

    def get_platform(self, url):
        if "weibo" in url:
            return "weibo"
        return "xhs"

    def get_platforms(self):
        return [
            {"id": "xhs", "name": "小红书", "supported_types": ["视频", "图文"]},
            {"id": "weibo", "name": "微博", "supported_types": ["视频"]},
        ]


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
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_dir = Path(self.tmp.name)
        self.config_path = self.config_dir / "config.toml"
        self.cookie_path = self.config_dir / "cookies.toml"
        self.patches = [
            patch.object(cli, "_config_store", lambda: ConfigStore(self.config_path)),
            patch.object(cli, "_cookie_store", lambda: FileCookieStore(self.cookie_path)),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(cli, "_has_cli_extra_dependencies", return_value=True),
            patch.object(cli, "_enable_completion", return_value=None),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_cli_extra_prints_install_hint(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(cli, "_has_cli_extra_dependencies", return_value=False),
            patch.object(cli, "_build_parser") as build_parser,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = cli.main(["platforms"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("未安装 ParseHub CLI 扩展依赖", stderr.getvalue())
        self.assertIn('pip install "parsehub[cli]"', stderr.getvalue())
        build_parser.assert_not_called()

    def test_missing_cli_extra_blocks_version_option(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(cli, "_has_cli_extra_dependencies", return_value=False),
            patch.object(cli, "_build_parser") as build_parser,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = cli.main(["--version"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("未安装 ParseHub CLI 扩展依赖", stderr.getvalue())
        build_parser.assert_not_called()

    def test_version_option_prints_package_version(self):
        with patch.object(cli, "_package_version", return_value="9.9.9"):
            code, stdout, stderr = self.run_cli(["--version"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "parsehub 9.9.9\n")
        self.assertEqual(stderr, "")

    def test_short_version_option_prints_package_version(self):
        with patch.object(cli, "_package_version", return_value="9.9.9"):
            code, stdout, stderr = self.run_cli(["-v"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "parsehub 9.9.9\n")
        self.assertEqual(stderr, "")

    def test_empty_args_print_help(self):
        code, stdout, stderr = self.run_cli([])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("ParseHub 命令行工具", stdout)
        self.assertIn("用法:", stdout)

    def test_parse_defaults_to_human_readable_chinese_summary(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
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
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1", "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["title"], "标题")

    def test_parse_compact_outputs_single_line_json(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1", "--compact"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertNotIn("\n  ", stdout)
        self.assertEqual(json.loads(stdout)["platform"], "xhs")

    def test_short_parse_alias_and_default_parse(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
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
        with patch.object(cli, "_new_parsehub", FakeParseHub):
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
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["d", "https://example.com/post/1", "--output-dir", "./out", "--json"])

        self.assertEqual(code, 0)
        self.assertIn("解析中...", stderr)
        data = json.loads(stdout)
        self.assertEqual(data["output_dir"], "/tmp/parsehub-output")
        self.assertEqual(data["media"]["path"], "/tmp/parsehub-output/0.mp4")
        self.assertEqual(FakeParseHub.instances[0].download_calls[0]["path"], "./out")

    def test_download_quiet_suppresses_feedback_and_progress_callback(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["dl", "https://example.com/post/1", "--quiet"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("下载完成: /tmp/parsehub-output", stdout)
        self.assertIsNone(FakeParseHub.instances[0].download_calls[0]["callback"])

    def test_download_no_progress_keeps_status_but_disables_callback(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["download", "https://example.com/post/1", "--no-progress"])

        self.assertEqual(code, 0)
        self.assertIn("下载完成: /tmp/parsehub-output", stdout)
        self.assertIn("解析中...", stderr)
        self.assertNotIn("下载中", stderr)
        self.assertIsNone(FakeParseHub.instances[0].download_calls[0]["callback"])

    def test_download_defaults_path_to_cwd_downloads(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["download", "https://example.com/post/1", "--quiet"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(FakeParseHub.instances[0].download_calls[0]["path"], Path.cwd() / "downloads")

    def test_platforms_outputs_aligned_human_readable_table(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["platforms"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        lines = stdout.splitlines()
        self.assertEqual(lines[0], "平台   名称    支持类型")
        self.assertEqual(lines[1], "-----  ------  --------")
        self.assertEqual(lines[2], "xhs    小红书  视频、图文")
        self.assertEqual(lines[3], "weibo  微博    视频")

    def test_short_platforms_alias_outputs_json(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["ls", "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            json.loads(stdout),
            [
                {"id": "xhs", "name": "小红书", "supported_types": ["视频", "图文"]},
                {"id": "weibo", "name": "微博", "supported_types": ["视频"]},
            ],
        )

    def test_set_proxy_sets_and_shows_parse_and_download_proxy(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            set_code, set_stdout, set_stderr = self.run_cli(["set", "proxy", "xhs", "http://proxy"])
            show_code, show_stdout, show_stderr = self.run_cli(["set", "show", "xhs"])

        self.assertEqual(set_code, 0)
        self.assertEqual(set_stderr, "")
        self.assertIn("已设置 xhs 的解析代理和下载代理。", set_stdout)
        self.assertIn("代理地址: http://proxy", set_stdout)
        self.assertEqual(show_code, 0)
        self.assertEqual(show_stderr, "")
        self.assertIn("解析代理: http://proxy", show_stdout)
        self.assertIn("下载代理: http://proxy", show_stdout)
        self.assertIn('parse_proxy = "http://proxy"', self.config_path.read_text())
        self.assertIn('download_proxy = "http://proxy"', self.config_path.read_text())

    def test_set_proxy_supports_targeted_clear(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            self.run_cli(["set", "proxy", "xhs", "http://parse", "--for", "parse"])
            self.run_cli(["set", "proxy", "xhs", "http://download", "--for", "download"])
            code, stdout, stderr = self.run_cli(["set", "proxy", "xhs", "--clear", "--for", "parse"])
            show_code, show_stdout, show_stderr = self.run_cli(["set", "show", "xhs"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("已清除 xhs 的解析代理", stdout)
        self.assertEqual(show_code, 0)
        self.assertEqual(show_stderr, "")
        self.assertIn("解析代理: 未设置", show_stdout)
        self.assertIn("下载代理: http://download", show_stdout)

    def test_set_cookie_sets_lists_and_clears_cookie_without_printing_value(self):
        prompt = Mock()
        prompt.read.return_value = "a=b; token=secret"
        with (
            patch.object(cli, "_new_parsehub", FakeParseHub),
            patch.object(cli, "_cookie_prompt", return_value=prompt),
        ):
            set_code, set_stdout, set_stderr = self.run_cli(["set", "cookie", "xhs"])
            list_code, list_stdout, list_stderr = self.run_cli(["set", "list"])
            clear_code, clear_stdout, clear_stderr = self.run_cli(["set", "cookie", "xhs", "--clear"])

        self.assertEqual(set_code, 0)
        self.assertEqual(set_stderr, "")
        self.assertIn("已保存 xhs Cookie", set_stdout)
        self.assertNotIn("secret", set_stdout)
        self.assertEqual(list_code, 0)
        self.assertEqual(list_stderr, "")
        self.assertIn("xhs", list_stdout)
        self.assertIn("✓", list_stdout)
        self.assertEqual(clear_code, 0)
        self.assertEqual(clear_stderr, "")
        self.assertIn("已清除 xhs Cookie。", clear_stdout)
        self.assertFalse(FileCookieStore(self.cookie_path).exists("xhs"))

    def test_parse_uses_saved_platform_proxy_and_cookie(self):
        ConfigStore(self.config_path).set_proxy("xhs", "http://parse-proxy", "parse")
        FileCookieStore(self.cookie_path).set("xhs", "saved=cookie")
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("平台: xhs", stdout)
        self.assertEqual(FakeParseHub.instances[0].parse_calls[0]["proxy"], "http://parse-proxy")
        self.assertEqual(FakeParseHub.instances[0].parse_calls[0]["cookie"], "saved=cookie")

    def test_download_uses_saved_platform_proxies_and_cookie(self):
        store = ConfigStore(self.config_path)
        store.set_proxy("xhs", "http://parse-proxy", "parse")
        store.set_proxy("xhs", "http://download-proxy", "download")
        FileCookieStore(self.cookie_path).set("xhs", "saved=cookie")
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["download", "https://example.com/post/1", "--quiet"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("下载完成", stdout)
        call = FakeParseHub.instances[0].download_calls[0]
        self.assertEqual(call["proxy"], "http://download-proxy")
        self.assertEqual(call["parse_proxy"], "http://parse-proxy")
        self.assertEqual(call["parse_cookie"], "saved=cookie")

    def test_cli_options_override_saved_platform_config(self):
        ConfigStore(self.config_path).set_proxy("xhs", "http://saved-proxy", "all")
        FileCookieStore(self.cookie_path).set("xhs", "saved=cookie")
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(
                [
                    "download",
                    "https://example.com/post/1",
                    "--quiet",
                    "--proxy",
                    "http://cli-download",
                    "--parse-proxy",
                    "http://cli-parse",
                    "--cookie",
                    "cli=cookie",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("下载完成", stdout)
        call = FakeParseHub.instances[0].download_calls[0]
        self.assertEqual(call["proxy"], "http://cli-download")
        self.assertEqual(call["parse_proxy"], "http://cli-parse")
        self.assertEqual(call["parse_cookie"], "cli=cookie")

    def test_parsehub_error_returns_one(self):
        with patch.object(cli, "_new_parsehub", ErrorParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("boom", stderr)
        self.assertIn("错误", stderr)

    def test_value_error_returns_one(self):
        with patch.object(cli, "_new_parsehub", ValueErrorParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("bad input", stderr)
        self.assertIn("错误", stderr)

    def test_keyboard_interrupt_returns_130(self):
        with patch.object(cli, "_new_parsehub", KeyboardInterruptParseHub):
            code, stdout, stderr = self.run_cli(["parse", "https://example.com/post/1"])

        self.assertEqual(code, 130)
        self.assertEqual(stdout, "")
        self.assertIn("已中断", stderr)

    def test_argparse_error_returns_two_in_chinese_with_hint(self):
        code, stdout, stderr = self.run_cli(["parse"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("错误", stderr)
        self.assertIn("提示", stderr)

    def test_top_level_help_uses_chinese_labels_and_examples(self):
        code, stdout, stderr = self.run_cli(["--help"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("用法:", stdout)
        self.assertIn("位置参数", stdout)
        self.assertIn("常用示例", stdout)
        self.assertIn("parsehub set proxy xhs", stdout)

    def test_set_proxy_missing_value_shows_actionable_example(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["set", "proxy", "xhs"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("缺少代理地址", stderr)
        self.assertIn("示例: parsehub set proxy xhs http://127.0.0.1:7890", stderr)
        self.assertIn("\n  示例:", stderr)

    def test_unknown_platform_error_lists_next_step(self):
        with patch.object(cli, "_new_parsehub", FakeParseHub):
            code, stdout, stderr = self.run_cli(["set", "show", "unknown"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("未知平台: unknown", stderr)
        self.assertIn("可用平台示例:", stderr)
        self.assertIn("查看全部平台: parsehub platforms", stderr)
        self.assertIn("\n  可用平台示例:", stderr)

    def test_set_missing_subcommand_hint_is_multiline(self):
        code, stdout, stderr = self.run_cli(["set"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("可用命令有 list、show、proxy、cookie", stderr)
        self.assertIn("\n示例: parsehub set show xhs", stderr)


if __name__ == "__main__":
    unittest.main()
