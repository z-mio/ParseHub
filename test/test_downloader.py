import contextlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

from parsehub.errors import DownloadError
from parsehub.utils.downloader import download


class RangeTestHandler(BaseHTTPRequestHandler):
    content: ClassVar[bytes] = b""
    support_range: ClassVar[bool] = True
    fail_all: ClassVar[bool] = False
    requests: ClassVar[list[tuple[str, str | None]]] = []

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_HEAD(self) -> None:
        self.__class__.requests.append(("HEAD", self.headers.get("Range")))
        if self.fail_all:
            self.send_response(500)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Length", str(len(self.content)))
        self.send_header("Accept-Ranges", "bytes" if self.support_range else "none")
        self.end_headers()

    def do_GET(self) -> None:
        range_header = self.headers.get("Range")
        self.__class__.requests.append(("GET", range_header))
        if self.fail_all:
            self.send_response(500)
            self.end_headers()
            return

        if range_header and self.support_range:
            start, end = self._parse_range(range_header)
            if start >= len(self.content):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(self.content)}")
                self.end_headers()
                return

            end = min(end, len(self.content) - 1)
            body = self.content[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.content)}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Content-Length", str(len(self.content)))
        self.send_header("Accept-Ranges", "none")
        self.end_headers()
        self.wfile.write(self.content)

    @staticmethod
    def _parse_range(header: str) -> tuple[int, int]:
        prefix = "bytes="
        if not header.startswith(prefix):
            return 0, 0
        start_text, end_text = header.removeprefix(prefix).split("-", 1)
        return int(start_text), int(end_text)


@contextlib.contextmanager
def range_server(*, content: bytes, support_range: bool = True, fail_all: bool = False):
    class Handler(RangeTestHandler):
        pass

    Handler.content = content
    Handler.support_range = support_range
    Handler.fail_all = fail_all
    Handler.requests = []

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/file.bin", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class DownloaderTest(unittest.IsolatedAsyncioTestCase):
    async def test_download_uses_range_parts_when_server_supports_range(self):
        content = bytes(range(251)) * 20
        progresses: list[tuple[int, int]] = []

        async def progress(current: int, total: int) -> None:
            progresses.append((current, total))

        with TemporaryDirectory() as tmp, range_server(content=content, support_range=True) as (url, handler):
            target = Path(tmp) / "video.bin"

            path = await download(
                url,
                target,
                progress=progress,
                connections=4,
                min_split_size=512,
                chunk_size=128,
            )

            self.assertEqual(Path(path), target)
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(progresses[-1], (len(content), len(content)))
            range_gets = [range_header for method, range_header in handler.requests if method == "GET" and range_header]
            self.assertGreaterEqual(len(range_gets), 2)
            self.assertFalse(list(Path(tmp).glob(".*.parsehub-tmp")))

    async def test_download_falls_back_to_single_request_when_range_is_ignored(self):
        content = b"fallback-body" * 100

        with TemporaryDirectory() as tmp, range_server(content=content, support_range=False) as (url, handler):
            target = Path(tmp) / "image.bin"

            await download(url, target, connections=4, min_split_size=10, chunk_size=32)

            self.assertEqual(target.read_bytes(), content)
            self.assertIn(("GET", "bytes=0-0"), handler.requests)
            self.assertIn(("GET", None), handler.requests)
            self.assertFalse(list(Path(tmp).glob(".*.parsehub-tmp")))

    async def test_download_keeps_existing_file_when_request_fails(self):
        with TemporaryDirectory() as tmp, range_server(content=b"new", support_range=True, fail_all=True) as (url, _):
            target = Path(tmp) / "video.bin"
            target.write_bytes(b"old")

            with self.assertRaises(DownloadError):
                await download(url, target, connections=4, max_retries=0)

            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse(list(Path(tmp).glob(".*.parsehub-tmp")))

    async def test_connections_one_uses_single_request(self):
        content = b"single" * 200

        with TemporaryDirectory() as tmp, range_server(content=content, support_range=True) as (url, handler):
            target = Path(tmp) / "single.bin"

            await download(url, target, connections=1, min_split_size=10)

            self.assertEqual(target.read_bytes(), content)
            range_gets = [range_header for method, range_header in handler.requests if method == "GET" and range_header]
            self.assertEqual(range_gets, [])


if __name__ == "__main__":
    unittest.main()
