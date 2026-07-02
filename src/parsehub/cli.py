from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import unicodedata
from dataclasses import asdict, is_dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

if TYPE_CHECKING:
    from .cli_config import AutoCookieStore, PlatformConfig

_COMMANDS = {"parse", "p", "download", "d", "dl", "platforms", "ls", "set"}
_CLI_EXTRA_MODULES = ("argcomplete", "platformdirs")


class _ChineseArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any):
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        add_help = bool(kwargs.pop("add_help", True))
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        if add_help:
            self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        translated = _translate_argparse_error(message)
        hint = _usage_hint(self.prog)
        self.exit(2, f"{self.prog}: 错误: {translated}{hint}\n")


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not _has_cli_extra_dependencies():
        _print_cli_extra_hint()
        return 1
    parser = _build_parser(Path(sys.argv[0]).name if argv is None else "parsehub")
    _enable_completion(parser)
    if not raw_argv:
        parser.print_help()
        return 0
    try:
        args = parser.parse_args(_normalize_argv(raw_argv))
        _finalize_output_args(args)
        return int(args.func(args))
    except SystemExit as e:
        return _normalize_exit_code(e.code)
    except ValueError as e:
        _print_error(e)
        return 1
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except Exception as e:
        _print_error(e)
        return 1


def _build_parser(prog: str) -> argparse.ArgumentParser:
    parser = _ChineseArgumentParser(
        prog=prog,
        description=(
            "ParseHub 命令行工具：解析和下载社交媒体内容。\n\n"
            "常用示例:\n"
            '  parsehub "分享文案或链接"\n'
            '  parsehub d "分享文案或链接" -o ./downloads\n'
            "  parsehub set proxy xhs http://127.0.0.1:7890\n"
            "  parsehub set cookie xhs"
        ),
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"parsehub {_package_version()}", help="显示当前版本"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse",
        aliases=["p"],
        help="解析链接或分享文案",
        description="解析链接或分享文案，未指定命令时也会默认执行此命令。",
    )
    parse_parser.add_argument("url_or_text", help="分享链接或包含链接的分享文案")
    parse_parser.add_argument("--proxy", help="解析代理，默认读取平台解析代理")
    parse_parser.add_argument("--cookie", help="解析 Cookie，默认读取平台 Cookie")
    _add_json_options(parse_parser)
    parse_parser.set_defaults(func=_cmd_parse)

    download_parser = subparsers.add_parser(
        "download",
        aliases=["d", "dl"],
        help="解析并下载媒体",
        description=(
            "解析并下载媒体。默认会自动读取该平台保存的解析代理、下载代理和 Cookie。\n\n"
            "示例:\n"
            '  parsehub d "https://..."\n'
            '  parsehub d "https://..." -o ./downloads\n'
            '  parsehub d "https://..." --parse-proxy http://127.0.0.1:7890'
        ),
    )
    download_parser.add_argument("url_or_text", help="分享链接或包含链接的分享文案")
    download_parser.add_argument("-o", "--output-dir", "--path", dest="path", help="下载保存目录")
    download_parser.add_argument("--proxy", "--download-proxy", dest="proxy", help="下载代理，默认读取平台下载代理")
    download_parser.add_argument("--parse-proxy", help="解析阶段代理，默认读取平台解析代理")
    download_parser.add_argument(
        "--cookie",
        "--parse-cookie",
        dest="parse_cookie",
        help="解析阶段 Cookie，默认读取平台 Cookie",
    )
    download_parser.add_argument(
        "-m", "--metadata", "--save-metadata", dest="save_metadata", action="store_true", help="保存 metadata.json"
    )
    download_parser.add_argument("-q", "--quiet", action="store_true", help="不输出状态和进度信息")
    download_parser.add_argument("--no-progress", action="store_true", help="不显示下载进度")
    download_parser.add_argument("--connections", type=int, default=4, help="单文件分片下载连接数，设为 1 可禁用分片")
    _add_json_options(download_parser)
    download_parser.set_defaults(func=_cmd_download)

    platforms_parser = subparsers.add_parser(
        "platforms",
        aliases=["ls"],
        help="列出支持的平台",
        description="列出 ParseHub 当前可识别的平台。配置平台代理和 Cookie 请使用 parsehub set。",
    )
    _add_json_options(platforms_parser)
    platforms_parser.set_defaults(func=_cmd_platforms)

    _add_set_commands(subparsers)

    return parser


def _package_version() -> str:
    try:
        return version("parsehub")
    except PackageNotFoundError:
        return "unknown"


def _add_set_commands(subparsers: argparse._SubParsersAction) -> None:
    set_parser = subparsers.add_parser(
        "set",
        help="设置平台代理和 Cookie",
        description=(
            "设置每个平台的解析代理、下载代理和 Cookie。\n\n"
            "常用示例:\n"
            "  parsehub set list\n"
            "  parsehub set show xhs\n"
            "  parsehub set proxy xhs http://127.0.0.1:7890\n"
            "  parsehub set proxy xhs http://127.0.0.1:7891 --for download\n"
            "  parsehub set cookie xhs"
        ),
    )
    set_subparsers = set_parser.add_subparsers(dest="set_command", metavar="command", required=True)

    list_parser = set_subparsers.add_parser(
        "list",
        help="列出平台代理和 Cookie 状态",
        description="列出所有平台的解析代理、下载代理和 Cookie 保存状态。",
    )
    _add_json_options(list_parser)
    list_parser.set_defaults(func=_cmd_platform_list)

    show_parser = set_subparsers.add_parser(
        "show",
        help="查看平台配置",
        description="查看某个平台当前保存的解析代理、下载代理和 Cookie 状态。\n\n示例: parsehub set show xhs",
    )
    _add_platform_argument(show_parser)
    _add_json_options(show_parser)
    show_parser.set_defaults(func=_cmd_platform_show)

    proxy_parser = set_subparsers.add_parser(
        "proxy",
        help="设置或清除平台代理",
        description=(
            "设置或清除平台代理。默认同时作用于解析代理和下载代理。\n\n"
            "示例:\n"
            "  parsehub set proxy xhs http://127.0.0.1:7890\n"
            "  parsehub set proxy xhs http://127.0.0.1:7891 --for download\n"
            "  parsehub set proxy xhs --clear"
        ),
    )
    _add_platform_argument(proxy_parser)
    proxy_parser.add_argument("proxy", nargs="?", help="代理地址，例如 http://127.0.0.1:7890")
    proxy_parser.add_argument(
        "--for",
        dest="proxy_target",
        choices=["parse", "download", "all"],
        default="all",
        help="代理用途：parse=解析阶段，download=下载阶段，all=两者都设置",
    )
    proxy_parser.add_argument("--clear", action="store_true", help="清除代理")
    proxy_parser.set_defaults(func=_cmd_platform_proxy)

    cookie_parser = set_subparsers.add_parser(
        "cookie",
        help="设置或清除平台 Cookie",
        description=(
            "保存或清除某个平台的 Cookie。设置时会隐藏输入，避免 Cookie 留在 shell 历史里。\n\n"
            "示例:\n"
            "  parsehub set cookie xhs\n"
            "  parsehub set cookie xhs --clear"
        ),
    )
    _add_platform_argument(cookie_parser)
    cookie_parser.add_argument("--clear", action="store_true", help="清除 Cookie")
    cookie_parser.set_defaults(func=_cmd_platform_cookie)


def _add_platform_argument(parser: argparse.ArgumentParser) -> None:
    action = parser.add_argument("platform", help="平台 ID，如 xhs")
    action.completer = _complete_platforms  # type: ignore[attr-defined]


def _add_json_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="输出 JSON，适合脚本处理")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pretty", dest="pretty", action="store_true", default=None, help="输出格式化 JSON")
    group.add_argument("--compact", dest="pretty", action="store_false", help="输出紧凑 JSON")


def _cmd_parse(args: argparse.Namespace) -> int:
    hub = _new_parsehub()
    platform_id = _detect_platform_id(hub, args.url_or_text)
    config = _load_platform_config(platform_id)
    proxy = args.proxy if args.proxy is not None else config.parse_proxy
    cookie = args.cookie if args.cookie is not None else _load_cookie(platform_id)
    data = hub.parse_sync(args.url_or_text, proxy=proxy, cookie=cookie).to_dict()
    if args.json:
        _print_json(data, pretty=args.pretty)
    else:
        _print_parse_summary(data)
    return 0


def _cmd_download(args: argparse.Namespace) -> int:
    hub = _new_parsehub()
    platform_id = _detect_platform_id(hub, args.url_or_text)
    config = _load_platform_config(platform_id)
    proxy = args.proxy if args.proxy is not None else config.download_proxy
    parse_proxy = args.parse_proxy if args.parse_proxy is not None else config.parse_proxy
    parse_cookie = args.parse_cookie if args.parse_cookie is not None else _load_cookie(platform_id)
    reporter = _ProgressReporter(enabled=not args.quiet and not args.no_progress)
    if not args.quiet:
        print("解析中...", file=sys.stderr)

    result = hub.download_sync(
        args.url_or_text,
        path=args.path or Path.cwd() / "downloads",
        callback=reporter if reporter.enabled else None,
        proxy=proxy,
        parse_proxy=parse_proxy,
        parse_cookie=parse_cookie,
        save_metadata=args.save_metadata,
        connections=args.connections,
    )
    reporter.finish()

    data = _download_result_to_dict(result)
    if args.json:
        _print_json(data, pretty=args.pretty)
    else:
        _print_download_summary(data)
    return 0


def _cmd_platforms(args: argparse.Namespace) -> int:
    platforms = _new_parsehub().get_platforms()
    if args.json:
        _print_json(platforms, pretty=args.pretty)
    else:
        _print_platforms_table(platforms)
    return 0


def _cmd_platform_list(args: argparse.Namespace) -> int:
    rows = _platform_config_rows()
    if args.json:
        _print_json(rows, pretty=args.pretty)
    else:
        _print_platform_config_table(rows)
    return 0


def _cmd_platform_show(args: argparse.Namespace) -> int:
    platform = _validate_platform(args.platform)
    config = _config_store().get_platform(platform)
    data = _platform_config_row(_platform_info_map().get(platform, {"id": platform, "name": platform}), config)
    if args.json:
        _print_json(data, pretty=args.pretty)
    else:
        _print_platform_config_detail(data)
    return 0


def _cmd_platform_proxy(args: argparse.Namespace) -> int:
    platform = _validate_platform(args.platform)
    if args.clear:
        if args.proxy:
            raise ValueError("清除代理时不需要填写代理地址。\n示例: parsehub set proxy xhs --clear")
        changed = _config_store().clear_proxy(platform, args.proxy_target)
        if changed:
            print(f"已清除 {platform} 的{_proxy_target_label(args.proxy_target)}。")
        else:
            print(f"{platform} 还没有配置{_proxy_target_label(args.proxy_target)}，无需清除。")
        return 0
    if not args.proxy:
        raise ValueError("缺少代理地址。\n示例: parsehub set proxy xhs http://127.0.0.1:7890")
    _config_store().set_proxy(platform, args.proxy, args.proxy_target)
    print(f"已设置 {platform} 的{_proxy_target_label(args.proxy_target)}。")
    print(f"代理地址: {args.proxy}")
    return 0


def _cmd_platform_cookie(args: argparse.Namespace) -> int:
    platform = _validate_platform(args.platform)
    store = _cookie_store()
    if args.clear:
        print(f"已清除 {platform} Cookie。" if store.delete(platform) else f"{platform} 还没有保存 Cookie，无需清除。")
        return 0
    store.set(platform, _cookie_prompt().read(platform))
    print(f"已保存 {platform} Cookie。之后解析或下载该平台内容时会自动使用。")
    return 0


def _print_error(error: Exception) -> None:
    lines = str(error).splitlines() or [error.__class__.__name__]
    print(f"错误: {lines[0]}", file=sys.stderr)
    for line in lines[1:]:
        print(f"  {line}", file=sys.stderr)


def _new_parsehub() -> Any:
    from . import ParseHub

    return ParseHub()


def _platform_config_type() -> type:
    from .cli_config import PlatformConfig

    return PlatformConfig


def _config_store() -> Any:
    from .cli_config import ConfigStore

    return ConfigStore()


def _cookie_store() -> Any:
    from .cli_config import AutoCookieStore

    return AutoCookieStore()


def _cookie_prompt() -> Any:
    from .cli_config import CookiePrompt

    return CookiePrompt()


def _load_platform_config(platform_id: str | None) -> PlatformConfig:
    if not platform_id:
        return cast("PlatformConfig", _platform_config_type()())
    return cast("PlatformConfig", _config_store().get_platform(platform_id))


def _load_cookie(platform_id: str | None) -> str | None:
    if not platform_id:
        return None
    value = _cookie_store().get(platform_id)
    return value if isinstance(value, str) or value is None else str(value)


def _detect_platform_id(hub: Any, url_or_text: str) -> str | None:
    get_platform = getattr(hub, "get_platform", None)
    if not callable(get_platform):
        return None
    platform = get_platform(url_or_text)
    return _platform_id(platform)


def _platform_id(platform: Any) -> str | None:
    value = getattr(platform, "id", None)
    if isinstance(value, str):
        return value
    if isinstance(platform, str):
        return platform
    return None


def _validate_platform(platform: str) -> str:
    platform = platform.lower()
    platform_ids = set(_supported_platform_ids())
    if platform_ids and platform not in platform_ids:
        sample = "、".join(sorted(platform_ids)[:8])
        raise ValueError(f"未知平台: {platform}\n可用平台示例: {sample}\n查看全部平台: parsehub platforms")
    return platform


def _supported_platform_ids() -> list[str]:
    return [str(platform.get("id")) for platform in _new_parsehub().get_platforms() if platform.get("id")]


def _platform_info_map() -> dict[str, dict[str, Any]]:
    return {str(platform.get("id")): platform for platform in _new_parsehub().get_platforms() if platform.get("id")}


def _platform_config_rows() -> list[dict[str, Any]]:
    config_store = _config_store()
    cookie_store = _cookie_store()
    return [
        _platform_config_row(platform, config_store.get_platform(str(platform["id"])), cookie_store=cookie_store)
        for platform in _new_parsehub().get_platforms()
    ]


def _platform_config_row(
    platform: dict[str, Any],
    config: PlatformConfig,
    *,
    cookie_store: AutoCookieStore | None = None,
) -> dict[str, Any]:
    platform_id = str(platform.get("id") or "")
    if cookie_store is None:
        cookie_store = _cookie_store()
    return {
        "id": platform_id,
        "name": str(platform.get("name") or ""),
        "parse_proxy": config.parse_proxy,
        "download_proxy": config.download_proxy,
        "cookie": cookie_store.exists(platform_id),
    }


def _print_json(data: Any, *, pretty: bool) -> None:
    kwargs: dict[str, Any] = {"ensure_ascii": False}
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


def _print_platform_config_table(rows: list[dict[str, Any]]) -> None:
    table = [
        (
            str(row["id"]),
            str(row["name"]),
            _status_text(bool(row["parse_proxy"])),
            _status_text(bool(row["download_proxy"])),
            _status_text(bool(row["cookie"])),
        )
        for row in rows
    ]
    id_width = max([_display_width("平台")] + [_display_width(row[0]) for row in table])
    name_width = max([_display_width("名称")] + [_display_width(row[1]) for row in table])
    print(f"{_pad_display('平台', id_width)}  {_pad_display('名称', name_width)}  解析代理  下载代理  Cookie")
    print(
        f"{_pad_display('-' * id_width, id_width)}  {_pad_display('-' * name_width, name_width)}  "
        "--------  --------  ------"
    )
    for platform_id, name, parse_proxy, download_proxy, cookie in table:
        print(
            f"{_pad_display(platform_id, id_width)}  {_pad_display(name, name_width)}  "
            f"{_pad_display(parse_proxy, 8)}  {_pad_display(download_proxy, 8)}  {cookie}"
        )


def _print_platform_config_detail(data: dict[str, Any]) -> None:
    print(f"平台: {data['id']}")
    if data.get("name"):
        print(f"名称: {data['name']}")
    print(f"解析代理: {data.get('parse_proxy') or '未设置'}")
    print(f"下载代理: {data.get('download_proxy') or '未设置'}")
    print(f"Cookie: {'已保存' if data.get('cookie') else '未保存'}")


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
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(cast(Any, value)))
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


def _usage_hint(prog: str) -> str:
    if prog.endswith(" set"):
        return "\n提示: 可用命令有 list、show、proxy、cookie。\n示例: parsehub set show xhs"
    if prog.endswith(" proxy"):
        return "\n提示: 设置代理需要平台和代理地址。\n示例: parsehub set proxy xhs http://127.0.0.1:7890"
    if prog.endswith(" cookie"):
        return "\n提示: 保存 Cookie 需要指定平台。\n示例: parsehub set cookie xhs"
    return "\n提示: 查看帮助请运行 parsehub --help"


def _proxy_target_label(target: str) -> str:
    return {"parse": "解析代理", "download": "下载代理", "all": "解析代理和下载代理"}[target]


def _status_text(value: bool) -> str:
    return "✓" if value else "✗"


def _complete_platforms(prefix: str, **_: Any) -> list[str]:
    return [platform for platform in _supported_platform_ids() if platform.startswith(prefix)]


def _has_cli_extra_dependencies() -> bool:
    return all(importlib.util.find_spec(module) is not None for module in _CLI_EXTRA_MODULES)


def _print_cli_extra_hint() -> None:
    print("错误: 未安装 ParseHub CLI 扩展依赖。", file=sys.stderr)
    print('请运行: pip install "parsehub[cli]"', file=sys.stderr)
    print('如果使用 uv: uv add "parsehub[cli]"', file=sys.stderr)


def _enable_completion(parser: argparse.ArgumentParser) -> None:
    import argcomplete

    argcomplete.autocomplete(parser)


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
                return (
                    f"下载中 {_progress_bar(percent)} {percent}% {_format_bytes(current)}/{_format_bytes(total)}",
                    percent,
                )
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
