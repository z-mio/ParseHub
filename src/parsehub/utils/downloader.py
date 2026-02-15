import asyncio
import os
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlparse

import aiofiles
import httpx


async def download(
    url: str,
    save_path: str | Path = None,
    *,
    headers: dict = None,
    proxies: httpx.Proxy = None,
    progress: Callable = None,
    progress_args: tuple = (),
    max_retries: int = 3,
    chunk_size: int = 8192,
) -> str:
    """
    :param url: 下载链接
    :param save_path: 保存路径, 默认保存到downloads文件夹, 如果路径以/结尾，则自动获取文件名
    :param headers: 请求头
    :param proxies: 代理
    :param progress: 下载进度回调函数
    :param progress_args: 下载进度回调函数参数
    :param max_retries: 最大重试次数
    :param chunk_size: 分块大小
    :return: 文件路径

    .. note::
        下载进度回调函数签名: async def progress(current: int, total: int, *args) -> None:
    """
    if headers is None:
        headers = {}

    save_dir, filename = _parse_save_path(save_path)

    for attempt in range(max_retries + 1):
        # 每次重试都创建新的 client，避免复用异常状态的连接池
        async with httpx.AsyncClient(proxy=proxies, headers=headers) as client:
            try:
                if not filename:
                    filename = await get_filename_by_url(url, client)
                if not filename:
                    raise ValueError("无法获取文件名")

                resolved_path = save_dir.joinpath(filename)
                resolved_path.parent.mkdir(parents=True, exist_ok=True)

                resume_pos = resolved_path.stat().st_size if resolved_path.exists() else 0

                # 设置Range头进行断点续传
                extra_headers = {}
                if resume_pos > 0:
                    extra_headers["Range"] = f"bytes={resume_pos}-"

                async with client.stream("GET", url, headers=extra_headers, follow_redirects=True) as r:
                    r.raise_for_status()

                    # 判断服务器是否真正支持断点续传（206 = Partial Content）
                    is_resumed = r.status_code == 206

                    # 如果发了 Range 但服务器返回 200，说明不支持续传，需要从头下载
                    if resume_pos > 0 and not is_resumed:
                        resume_pos = 0

                    content_length = r.headers.get("Content-Length")
                    if content_length:
                        total_size = int(content_length)
                        if is_resumed:
                            total_size += resume_pos
                    else:
                        total_size = 0

                    current = resume_pos if is_resumed else 0

                    file_mode = "ab" if is_resumed else "wb"

                    async with aiofiles.open(file=resolved_path, mode=file_mode) as f:
                        async for chunk in r.aiter_bytes(chunk_size=chunk_size):
                            if chunk:
                                await f.write(chunk)
                                current += len(chunk)
                                if progress:
                                    await progress(current, total_size, *progress_args)

                    # 完整性校验
                    if 0 < total_size != current:
                        raise DownloadError(f"下载不完整: 期望 {total_size} 字节, 实际 {current} 字节")

                    return str(resolved_path)

            except (
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ) as e:
                if attempt == max_retries:
                    raise DownloadError(f"连接超时: {e}") from e
                await asyncio.sleep(2**attempt)
                continue

            except (
                httpx.ConnectError,
                httpx.RemoteProtocolError,
                httpx.ReadError,
            ) as e:
                if attempt == max_retries:
                    raise DownloadError(f"网络连接错误: {e}") from e
                await asyncio.sleep(2**attempt)
                continue

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 416:
                    # Range Not Satisfiable: 文件可能已完整或服务器不支持续传
                    if filename:
                        p = save_dir.joinpath(filename)
                        if p.exists():
                            p.unlink()
                    if attempt == max_retries:
                        raise DownloadError(f"HTTP错误: {e.response.status_code}") from e
                    continue
                else:
                    raise DownloadError(f"HTTP错误: {e.response.status_code}") from e

            except (DownloadError, ValueError):
                raise

            except Exception as e:
                if attempt == max_retries:
                    raise DownloadError(f"下载失败: {e}") from e
                await asyncio.sleep(2**attempt)
                continue

    raise DownloadError("达到最大重试次数，下载失败")


def _parse_save_path(save_path: str | Path | None) -> tuple[Path, str | None]:
    """解析保存路径，返回 (目录, 文件名或None)"""
    if not save_path:
        return Path.cwd().joinpath("downloads"), None

    save_path = str(save_path)
    save_dir, filename = os.path.split(save_path)
    save_dir = Path(os.path.abspath(save_dir)) if save_dir else Path.cwd().joinpath("downloads")

    # 空文件名意味着需要自动获取
    return save_dir, filename if filename else None


async def get_filename_by_url(url: str, client: httpx.AsyncClient) -> str | None:
    """从 URL 或 HTTP 响应头中获取文件名"""
    try:
        response = await client.head(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        # HEAD 请求失败时，回退到从 URL 路径中解析
        pass
    else:
        if content_disposition := response.headers.get("content-disposition"):
            if filename := _parse_content_disposition(content_disposition):
                return _sanitize_filename(filename)

    # 从 URL 路径中提取文件名（去除查询参数和片段）
    parsed = urlparse(url)
    path = unquote(parsed.path).removesuffix("/")
    filename = path.split("/")[-1] if path else None
    return _sanitize_filename(filename) if filename else None


def _parse_content_disposition(header: str) -> str | None:
    """解析 Content-Disposition 头中的文件名，支持 filename*= 和带引号的 filename="""
    # 优先匹配 RFC 5987 编码: filename*=UTF-8''encoded_name
    if match := re.search(r"filename\*\s*=\s*[\w-]+'[^']*'(.+?)(?:;|$)", header):
        return unquote(match.group(1).strip())

    # 匹配带引号的: filename="name.ext"
    if match := re.search(r'filename\s*=\s*"([^"]+)"', header):
        return match.group(1).strip()

    # 匹配不带引号的: filename=name.ext
    if match := re.search(r"filename\s*=\s*([^\s;]+)", header):
        return match.group(1).strip()

    return None


def _sanitize_filename(filename: str) -> str:
    """清理文件名中不安全的字符"""
    # 移除 Windows 不允许的字符
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # 限制长度
    return filename[:255] if filename else filename


class DownloadError(Exception):
    pass
