from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from . import ParseHub
from .errors import ParseHubError


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        return args.func(args)
    except SystemExit as e:
        return _normalize_exit_code(e.code)
    except (ParseHubError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as e:
        print(e, file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parsehub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse a shared URL or text")
    parse_parser.add_argument("url_or_text", help="Shared URL or text containing a URL")
    parse_parser.add_argument("--proxy", help="Proxy used while parsing")
    parse_parser.add_argument("--cookie", help="Cookie used while parsing")
    _add_json_options(parse_parser)
    parse_parser.set_defaults(func=_cmd_parse)

    download_parser = subparsers.add_parser("download", help="Parse and download media")
    download_parser.add_argument("url_or_text", help="Shared URL or text containing a URL")
    download_parser.add_argument("-o", "--path", help="Directory to save downloaded media")
    download_parser.add_argument("--proxy", help="Proxy used while downloading")
    download_parser.add_argument("--parse-proxy", help="Proxy used while parsing")
    download_parser.add_argument("--parse-cookie", help="Cookie used while parsing")
    download_parser.add_argument("--save-metadata", action="store_true", help="Save metadata.json next to downloaded media")
    _add_json_options(download_parser)
    download_parser.set_defaults(func=_cmd_download)

    platforms_parser = subparsers.add_parser("platforms", help="List supported platforms")
    _add_json_options(platforms_parser)
    platforms_parser.set_defaults(func=_cmd_platforms)

    return parser


def _add_json_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pretty", dest="pretty", action="store_true", default=True, help="Print indented JSON")
    group.add_argument("--compact", dest="pretty", action="store_false", help="Print compact JSON")


def _cmd_parse(args: argparse.Namespace) -> int:
    result = ParseHub().parse_sync(args.url_or_text, proxy=args.proxy, cookie=args.cookie)
    _print_json(result.to_dict(), pretty=args.pretty)
    return 0


def _cmd_download(args: argparse.Namespace) -> int:
    result = ParseHub().download_sync(
        args.url_or_text,
        path=args.path or Path.cwd() / "downloads",
        proxy=args.proxy,
        parse_proxy=args.parse_proxy,
        parse_cookie=args.parse_cookie,
        save_metadata=args.save_metadata,
    )
    _print_json(_download_result_to_dict(result), pretty=args.pretty)
    return 0


def _cmd_platforms(args: argparse.Namespace) -> int:
    _print_json(ParseHub().get_platforms(), pretty=args.pretty)
    return 0


def _print_json(data: Any, *, pretty: bool) -> None:
    kwargs = {"ensure_ascii": False}
    if pretty:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    print(json.dumps(_jsonable(data), **kwargs))


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


def _normalize_exit_code(code: Any) -> int:
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
