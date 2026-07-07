import asyncio
import json
import os
import signal
import sys
import tempfile
from collections import deque
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from loguru import logger

from ...types import (
    AnyParseResult,
    DownloadError,
    DownloadResult,
    ParseError,
    ProgressCallback,
    VideoFile,
    VideoParseResult,
    VideoRef,
)
from .base import BaseParser

# 用一个不会和 yt-dlp 普通日志冲突的前缀标记进度行，stdout/stderr 读取时只解析这类行。
PROGRESS_PREFIX = "__PARSEHUB_YTDLP_PROGRESS__"

# yt-dlp CLI 进度模板, download: 是 yt-dlp 的模板作用域前缀；
# 后续字段用 tab 分隔，便于还原成 progress_hooks 风格的 dict。
PROGRESS_TEMPLATE = (
    f"download:{PROGRESS_PREFIX}"
    "%(progress.status)s\t"
    "%(progress.downloaded_bytes)s\t"
    "%(progress.total_bytes)s\t"
    "%(progress.total_bytes_estimate)s\t"
    "%(progress.fragment_index)s\t"
    "%(progress.fragment_count)s"
)

# 子进程失败时只保留尾部日志用于错误信息，避免长输出占用过多内存或污染异常文本。
TAIL_LINES = 100
TAIL_CHARS = 16_000


class MonotonicDownloadProgress:
    def __init__(self, *, start: float = 0.0, end: float = 100.0, min_step: float = 0.1) -> None:
        self.start = start
        self.end = end
        self.min_step = min_step
        self.current = start

    def update(self, d: dict[str, Any]) -> float | None:
        status = d.get("status")

        if status == "downloading":
            percent = self._download_percent(d)
            if percent is None:
                return None

            mapped = self.start + percent * (self.end - self.start) / 100

            if mapped >= self.current + self.min_step:
                self.current = mapped
                return round(self.current, 1)

        elif status == "finished" and self.current < self.end:
            self.current = self.end
            return round(self.current, 1)

        return None

    @staticmethod
    def _download_percent(d: dict[str, Any]) -> float | None:
        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        if downloaded == total == 1024:
            return None

        if total > 0:
            return min(downloaded / total * 100, 100)

        # 分片下载有时没有稳定总大小，但有 frag 进度；作为兜底
        frag_index = d.get("fragment_index")
        frag_count = d.get("fragment_count")
        if isinstance(frag_index, int | float) and isinstance(frag_count, int | float) and frag_count:
            return min(float(frag_index) / float(frag_count) * 100, 100.0)

        return None


def _yt_dlp_base_cmd() -> list[str]:
    return [sys.executable, "-m", "yt_dlp"]


def _subprocess_kwargs() -> dict[str, Any]:
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    if os.name == "posix":
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
        except Exception:
            proc.terminate()
    else:
        proc.terminate()

    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
        return
    except TimeoutError:
        pass

    if proc.returncode is not None:
        return

    if os.name == "posix":
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception:
            proc.kill()
    else:
        proc.kill()
    await proc.wait()


@contextmanager
def _temporary_text_file(content: str, *, suffix: str) -> Iterator[str]:
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=suffix) as f:
            path = f.name
            f.write(content)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        yield path
    finally:
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.debug("删除 yt-dlp 临时文件失败: {}", e)


@asynccontextmanager
async def _materialize_cookie(cookie_text: str | None) -> AsyncIterator[list[str]]:
    if not cookie_text:
        yield []
        return

    with _temporary_text_file(cookie_text, suffix=".cookies.txt") as path:
        yield ["--cookies", path]


@asynccontextmanager
async def _materialize_info_json(info_json: dict[str, Any]) -> AsyncIterator[str]:
    content = json.dumps(info_json, ensure_ascii=False)
    with _temporary_text_file(content, suffix=".info.json") as path:
        yield path


def _format_tail(tail: deque[str]) -> str:
    return "".join(tail)[-TAIL_CHARS:].strip()


def _ytdlp_error(returncode: int, stdout_tail: deque[str], stderr_tail: deque[str]) -> str:
    detail = _format_tail(stderr_tail) or _format_tail(stdout_tail) or "未知错误"
    return f"yt-dlp exited with code {returncode}: {detail}"


def _decode_output(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _json_from_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise RuntimeError("yt-dlp 未输出 JSON")

    try:
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return cast(dict[str, Any], json.loads(text[start : end + 1]))


def _optional_number(value: str) -> int | float | None:
    value = value.strip()
    if not value or value in {"NA", "None", "none", "null"}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return number


def _parse_progress_line(line: str) -> dict[str, Any] | None:
    index = line.find(PROGRESS_PREFIX)
    if index == -1:
        return None

    payload = line[index + len(PROGRESS_PREFIX) :].strip()
    parts = payload.split("\t")
    if len(parts) < 6:
        return None

    return {
        "status": parts[0],
        "downloaded_bytes": _optional_number(parts[1]),
        "total_bytes": _optional_number(parts[2]),
        "total_bytes_estimate": _optional_number(parts[3]),
        "fragment_index": _optional_number(parts[4]),
        "fragment_count": _optional_number(parts[5]),
    }


async def _run_ytdlp_json(
    url: str,
    cli_args: list[str],
    *,
    proxy: str | None = None,
    cookie_text: str | None = None,
) -> dict[str, Any]:
    async with _materialize_cookie(cookie_text) as cookie_args:
        argv = [
            *_yt_dlp_base_cmd(),
            *cli_args,
            "--dump-single-json",
            "--no-download",
            "--no-warnings",
            *cookie_args,
        ]
        if proxy:
            argv.extend(["--proxy", proxy])
        argv.append(url)

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **_subprocess_kwargs(),
        )
        try:
            stdout, stderr = await proc.communicate()
        except asyncio.CancelledError:
            await _terminate_process(proc)
            raise

    stdout_text = _decode_output(stdout)
    stderr_text = _decode_output(stderr)
    if proc.returncode:
        stdout_tail = deque([stdout_text], maxlen=TAIL_LINES)
        stderr_tail = deque([stderr_text], maxlen=TAIL_LINES)
        raise RuntimeError(_ytdlp_error(proc.returncode, stdout_tail, stderr_tail))

    try:
        return _json_from_stdout(stdout_text)
    except Exception as e:
        detail = stderr_text.strip() or str(e)
        raise RuntimeError(f"解析 yt-dlp JSON 失败: {detail}") from e


async def _read_ytdlp_stream(
    stream: asyncio.StreamReader,
    tail: deque[str],
    progress: MonotonicDownloadProgress | None,
    callback: ProgressCallback | None,
    callback_args: tuple,
    callback_kwargs: dict,
) -> None:
    while line := await stream.readline():
        text = _decode_output(line)
        progress_data = _parse_progress_line(text)
        if progress_data and progress and callback:
            count = progress.update(progress_data)
            if count is not None:
                await callback(int(count), 100, "bytes", *callback_args, **callback_kwargs)
            continue
        tail.append(text)


async def _run_ytdlp_download(
    info_json: dict[str, Any],
    cli_args: list[str],
    *,
    outtmpl: str,
    connections: int,
    proxy: str | None = None,
    callback: ProgressCallback | None = None,
    callback_args: tuple = (),
    callback_kwargs: dict | None = None,
) -> None:
    callback_kwargs = callback_kwargs or {}
    stdout_tail: deque[str] = deque(maxlen=TAIL_LINES)
    stderr_tail: deque[str] = deque(maxlen=TAIL_LINES)
    progress = MonotonicDownloadProgress(start=0, end=99) if callback else None

    async with _materialize_info_json(info_json) as info_path:
        argv = [*_yt_dlp_base_cmd(), *cli_args]
        if callback:
            argv = [arg for arg in argv if arg not in {"--quiet", "--no-progress"}]
            argv.extend(["--newline", "--progress-template", PROGRESS_TEMPLATE])
        argv.extend(["--load-info-json", info_path, "-o", outtmpl, "-N", str(connections)])
        if proxy:
            argv.extend(["--proxy", proxy])

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **_subprocess_kwargs(),
        )
        if proc.stdout is None or proc.stderr is None:
            await _terminate_process(proc)
            raise RuntimeError("yt-dlp 子进程 stdout/stderr 未正确初始化")

        stdout_task = asyncio.create_task(
            _read_ytdlp_stream(proc.stdout, stdout_tail, progress, callback, callback_args, callback_kwargs)
        )
        stderr_task = asyncio.create_task(
            _read_ytdlp_stream(proc.stderr, stderr_tail, progress, callback, callback_args, callback_kwargs)
        )
        wait_task = asyncio.create_task(proc.wait())

        try:
            returncode = await wait_task
            await asyncio.gather(stdout_task, stderr_task)
        except asyncio.CancelledError:
            await _terminate_process(proc)
            for task in (stdout_task, stderr_task, wait_task):
                task.cancel()
            await asyncio.gather(stdout_task, stderr_task, wait_task, return_exceptions=True)
            raise
        except Exception:
            await _terminate_process(proc)
            for task in (stdout_task, stderr_task, wait_task):
                task.cancel()
            await asyncio.gather(stdout_task, stderr_task, wait_task, return_exceptions=True)
            raise

    if returncode:
        raise RuntimeError(_ytdlp_error(returncode, stdout_tail, stderr_tail))


def _remove_subtitle_args(cli_args: list[str]) -> list[str]:
    remove_with_value = {"--sub-format", "--sub-langs"}
    remove_flags = {"--write-auto-subs", "--write-subs"}
    result: list[str] = []
    skip_next = False
    for arg in cli_args:
        if skip_next:
            skip_next = False
            continue
        if arg in remove_flags:
            continue
        if arg in remove_with_value:
            skip_next = True
            continue
        result.append(arg)
    return result


class YtParser(BaseParser, register=False):
    """yt-dlp解析器"""

    async def _do_parse(self, raw_url: str) -> AnyParseResult:
        video_info = await self._parse(raw_url)
        return YtVideoParseResult(
            dl=video_info,
            title=video_info.title,
            content=video_info.description,
            video=VideoRef(
                url=raw_url,
                thumb_url=video_info.thumbnail,
                width=video_info.width,
                height=video_info.height,
                duration=video_info.duration,
            ),
        )

    async def _parse(self, url: str) -> "YtVideoInfo":
        try:
            dl = await asyncio.wait_for(self._extract_info(url), timeout=30)
        except TimeoutError as e:
            raise ParseError("解析视频信息超时") from e
        except Exception as e:
            raise ParseError(f"解析视频信息失败: {str(e)}") from e

        if dl.get("_type") and dl["_type"] == "playlist":
            entries = dl.get("entries") or []
            if not entries:
                raise ParseError("解析视频信息失败: playlist entries is empty")
            dl = entries[0]
            url = dl.get("webpage_url") or url
        title = dl["title"]
        duration = dl.get("duration", 0)
        thumbnail = dl["thumbnail"]
        description = dl["description"]
        width = dl.get("width", 0)
        height = dl.get("height", 0)
        return YtVideoInfo(
            title=title,
            description=description,
            thumbnail=thumbnail,
            duration=duration,
            url=url,
            width=width,
            height=height,
            cli_args=self.cli_args,
            info_json=dl,
        )

    async def _extract_info(self, url: str) -> dict[str, Any]:
        try:
            return await _run_ytdlp_json(
                url,
                self.cli_args,
                proxy=self.proxy,
                cookie_text=self.get_cookie_text(),
            )
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            raise RuntimeError(error_msg) from None

    def get_cookie_text(self) -> str | None:
        return None

    @property
    def cli_args(self) -> list[str]:
        return [
            "--quiet",  # 不输出日志
            "--no-progress",  # 不输出下载进度
            "--playlist-items",
            "1",  # 分p列表默认解析第一个
        ]


class YtVideoParseResult(VideoParseResult):
    def __init__(
        self,
        dl: "YtVideoInfo",
        title: str | None,
        video: VideoRef | None = None,
        content: str | None = None,
    ):
        """dl: yt-dlp解析结果"""
        self.dl = dl
        super().__init__(title=title, video=video, content=content)

    async def _do_download(
        self,
        *,
        output_dir: Path,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
        proxy: str | None = None,
        headers: dict | None = None,
        connections: int = 4,
    ) -> "DownloadResult":
        if callback_kwargs is None:
            callback_kwargs = {}
        output_dir_path = Path(output_dir)

        cli_args = self.dl.cli_args.copy()
        outtmpl = f"{output_dir_path.joinpath(self.name)}.%(ext)s"

        await self._run_download(
            cli_args,
            outtmpl=outtmpl,
            connections=connections,
            proxy=proxy,
            callback=callback,
            callback_args=callback_args,
            callback_kwargs=callback_kwargs,
        )

        v = (
            list(output_dir_path.glob("*.mp4"))
            or list(output_dir_path.glob("*.mkv"))
            or list(output_dir_path.glob("*.webm"))
        )
        if not v:
            raise DownloadError("下载失败 -1")

        if callback:
            await callback(100, 100, "bytes", *callback_args, **callback_kwargs)

        video_path = v[0]
        return DownloadResult(
            VideoFile(
                path=str(video_path),
                height=self.dl.height,
                width=self.dl.width,
                duration=self.dl.duration,
            ),
            output_dir,
        )

    async def _run_download(
        self,
        cli_args: list[str],
        count: int = 0,
        *,
        outtmpl: str,
        connections: int,
        proxy: str | None = None,
        callback: ProgressCallback | None = None,
        callback_args: tuple = (),
        callback_kwargs: dict | None = None,
    ) -> None:
        if count > 2:
            raise DownloadError("下载失败 -2")

        try:
            await _run_ytdlp_download(
                self.dl.info_json,
                cli_args,
                outtmpl=outtmpl,
                connections=connections,
                proxy=proxy,
                callback=callback,
                callback_args=callback_args,
                callback_kwargs=callback_kwargs,
            )
        except RuntimeError as e:
            error = str(e)
            if any(
                msg in error
                for msg in (
                    "Unable to download video subtitles",
                    "Requested format is not available",
                )
            ):
                await self._run_download(
                    _remove_subtitle_args(cli_args),
                    count + 1,
                    outtmpl=outtmpl,
                    connections=connections,
                    proxy=proxy,
                    callback=callback,
                    callback_args=callback_args,
                    callback_kwargs=callback_kwargs,
                )
                return
            raise DownloadError(f"下载失败: {error}") from e

        except Exception as e:
            raise DownloadError(f"下载失败: {str(e)}") from e


@dataclass
class YtVideoInfo:
    """raw_video_info: yt-dlp解析结果"""

    title: str
    description: str
    thumbnail: str
    url: str
    cli_args: list[str]
    info_json: dict[str, Any]
    duration: int = 0
    width: int = 0
    height: int = 0
