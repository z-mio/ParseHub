from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from . import ParseHub
from .errors import ParseHubError

_COMMANDS = {"parse", "p", "download", "d", "dl", "platforms", "ls"}


class _ChineseArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: 错误: {_translate_argparse_error(message)}\n")


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser(Path(sys.argv[0]).name if argv is None else "parsehub")
    try:
        args = parser.parse_args(_normalize_argv(raw_argv))
        _finalize_output_args(args)
        return args.func(args)
    except SystemExit as e:
        return _normalize_exit_code(e.code)
    except (ParseHubError, ValueError) as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


def _build_parser(prog: str) -> argparse.ArgumentParser:
    parser = _ChineseArgumentParser(
        prog=prog,
        description="ParseHub 命令行工具：解析和下载社交媒体内容。",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="命令", required=True)

    parse_parser = subparsers.add_parser("parse", aliases=["p"], help="解析链接或分享文案")
    parse_parser.add_argument("url_or_text", help="分享链接或包含链接的分享文案")
    parse_parser.add_argument("--proxy", help="解析代理")
    parse_parser.add_argument("--cookie", help="解析 Cookie")
    _add_json_options(parse_parser)
    parse_parser.set_defaults(func=_cmd_parse)

    download_parser = subparsers.add_parser("download", aliases=["d", "dl"], help="解析并下载媒体")
    download_parser.add_argument("url_or_text", help="分享链接或包含链接的分享文案")
    download_parser.add_argument("-o", "--output-dir", "--path", dest="path", help="下载保存目录")
    download_parser.add_argument("--proxy", help="下载代理")
    download_parser.add_argument("--parse-proxy", help="解析阶段代理")
    download_parser.add_argument("--parse-cookie", help="解析阶段 Cookie")
    download_parser.add_argument("-m", "--metadata", "--save-metadata", dest="save_metadata", action="store_true", help="保存 metadata.json")
    download_parser.add_argument("-q", "--quiet", action="store_true", help="不输出状态和进度信息")
    download_parser.add_argument("--no-progress", action="store_true", help="不显示下载进度")
    _add_json_options(download_parser)
    download_parser.set_defaults(func=_cmd_download)

    platforms_parser = subparsers.add_parser("platforms", aliases=["ls"], help="列出支持的平台")
    _add_json_options(platforms_parser)
    platforms_parser.set_defaults(func=_cmd_platforms)

    return parser


def _add_json_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="输出 JSON，适合脚本处理")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pretty", dest="pretty", action="store_true", default=None, help="输出格式化 JSON")
    group.add_argument("--compact", dest="pretty", action="store_false", help="输出紧凑 JSON")


def _cmd_parse(args: argparse.Namespace) -> int:
    data = ParseHub().parse_sync(args.url_or_text, proxy=args.proxy, cookie=args.cookie).to_dict()
    if args.json:
        _print_json(data, pretty=args.pretty)
    else:
        _print_parse_summary(data)
    return 0


def _cmd_download(args: argparse.Namespace) -> int:
    reporter = _ProgressReporter(enabled=not args.quiet and not args.no_progress)
    if not args.quiet:
        print("解析中...", file=sys.stderr)

    result = ParseHub().download_sync(
        args.url_or_text,
        path=args.path or Path.cwd() / "downloads",
        callback=reporter if reporter.enabled else None,
        proxy=args.proxy,
        parse_proxy=args.parse_proxy,
        parse_cookie=args.parse_cookie,
        save_metadata=args.save_metadata,
    )
    reporter.finish()

    data = _download_result_to_dict(result)
    if args.json:
        _print_json(data, pretty=args.pretty)
    else:
        _print_download_summary(data)
    return 0


def _cmd_platforms(args: argparse.Namespace) -> int:
    platforms = ParseHub().get_platforms()
    if args.json:
        _print_json(platforms, pretty=args.pretty)
    else:
        _print_platforms_table(platforms)
    return 0


def _print_json(data: Any, *, pretty: bool) -> None:
    kwargs = {"ensure_ascii": False}
    if pretty:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    print(json.dumps(_jsonable(data), **kwargs))


def _print_platforms_table(platforms: list[dict[str, Any]]) -> None:
    rows = [
        (
            str(platform.get("id") or ""),
            str(platform.get("name") or ""),
            "、".join(platform.get("supported_types", [])),
        )
        for platform in platforms
    ]
    id_width = max([_display_width("平台")] + [_display_width(row[0]) for row in rows])
    name_width = max([_display_width("名称")] + [_display_width(row[1]) for row in rows])
    print(f"{_pad_display('平台', id_width)}  {_pad_display('名称', name_width)}  支持类型")
    print(f"{_pad_display('-' * id_width, id_width)}  {_pad_display('-' * name_width, name_width)}  --------")
    for platform_id, name, supported_types in rows:
        print(f"{_pad_display(platform_id, id_width)}  {_pad_display(name, name_width)}  {supported_types}")


def _print_parse_summary(data: dict[str, Any]) -> None:
    print(f"平台: {data.get('platform') or '-'}")
    print(f"类型: {data.get('type') or '-'}")
    if data.get("title"):
        print(f"标题: {data['title']}")
    if data.get("content"):
        print(f"正文: {data['content']}")
    if data.get("raw_url"):
        print(f"原链接: {data['raw_url']}")
    media = data.get("media")
    if media:
        print(f"媒体: {_summarize_media(media)}")


def _print_download_summary(data: dict[str, Any]) -> None:
    print(f"下载完成: {data['output_dir']}")
    paths = _media_paths(data.get("media"))
    if paths:
        print("媒体文件:")
        for path in paths:
            print(f"  {path}")


def _summarize_media(media: Any) -> str:
    if isinstance(media, list):
        return f"{len(media)} 个"
    if isinstance(media, dict):
        return str(media.get("url") or media.get("path") or "1 个")
    return "1 个"


def _media_paths(media: Any) -> list[str]:
    if isinstance(media, list):
        paths = []
        for item in media:
            paths.extend(_media_paths(item))
        return paths
    if isinstance(media, dict):
        return [str(path) for path in (media.get("path"), media.get("video_path")) if path]
    return []


def _download_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "output_dir": str(result.output_dir),
        "media": _jsonable(result.media),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _display_width(value: str) -> int:
    width = 0
    for char in value:
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def _pad_display(value: str, width: int) -> str:
    return value + " " * max(0, width - _display_width(value))


def _normalize_argv(argv: list[str]) -> list[str]:
    if argv and argv[0] not in _COMMANDS and not argv[0].startswith("-"):
        return ["parse", *argv]
    return argv


def _finalize_output_args(args: argparse.Namespace) -> None:
    if getattr(args, "pretty", None) is not None:
        args.json = True
    if getattr(args, "pretty", None) is None:
        args.pretty = True


def _normalize_exit_code(code: Any) -> int:
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _translate_argparse_error(message: str) -> str:
    replacements = {
        "the following arguments are required:": "缺少必填参数:",
        "unrecognized arguments:": "无法识别的参数:",
        "invalid choice:": "无效选择:",
        "expected one argument": "需要一个参数",
    }
    for source, target in replacements.items():
        message = message.replace(source, target)
    return message


class _ProgressReporter:
    def __init__(self, *, enabled: bool, stream: Any = None):
        self.enabled = enabled
        self.stream = sys.stderr if stream is None else stream
        self._dynamic = bool(getattr(self.stream, "isatty", lambda: False)())
        self._last_marker: Any = None
        self._active = False

    async def __call__(self, current: int, total: int, unit: str, *args: Any, **kwargs: Any) -> None:
        if not self.enabled:
            return
        line, marker = self._format(current, total, unit)
        if marker == self._last_marker:
            return
        self._last_marker = marker
        self._active = True
        if self._dynamic:
            print(f"\r{line}", end="", file=self.stream, flush=True)
        else:
            print(line, file=self.stream)

    def finish(self) -> None:
        if self.enabled and self._active and self._dynamic:
            print(file=self.stream)

    def _format(self, current: int, total: int, unit: str) -> tuple[str, Any]:
        if unit == "bytes":
            if total > 0:
                percent = min(100, int(current * 100 / total))
                return f"下载中 {_progress_bar(percent)} {percent}% {_format_bytes(current)}/{_format_bytes(total)}", percent
            return f"下载中 {_format_bytes(current)}", current
        if total > 0:
            percent = min(100, int(current * 100 / total))
            return f"下载中 {_progress_bar(percent)} {current}/{total}", (current, total)
        return f"下载中 {current}", current


def _progress_bar(percent: int, width: int = 20) -> str:
    filled = round(width * percent / 100)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size:.1f}GB"


if __name__ == "__main__":
    raise SystemExit(main())
