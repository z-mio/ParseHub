import asyncio
import os
import re
from collections.abc import Callable
from pathlib import Path

import aiofiles
import httpx


async def download_file(
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
    if not headers:
        headers = {}

    async with httpx.AsyncClient(proxy=proxies, headers=headers) as client:
        save_dir, filename = os.path.split(save_path) if save_path else (None, None)
        save_dir = Path(os.path.abspath(save_dir)) if save_dir else Path.cwd().joinpath("downloads")
        filename = filename or await get_filename_by_url(url, client)

        if not filename:
            raise ValueError("无法获取文件名")

        save_path = save_dir.joinpath(filename)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        resume_pos = 0
        if save_path.exists():
            resume_pos = save_path.stat().st_size

        for attempt in range(max_retries + 1):
            try:
                # 设置Range头进行断点续传
                current_headers = headers.copy()
                if resume_pos > 0:
                    current_headers["Range"] = f"bytes={resume_pos}-"

                async with client.stream("GET", url, headers=current_headers, follow_redirects=True) as r:
                    r.raise_for_status()

                    # 获取文件总大小
                    content_length = r.headers.get("Content-Length")
                    if content_length:
                        total_size = int(content_length)
                        if resume_pos > 0:
                            total_size += resume_pos
                    else:
                        total_size = 0

                    current = resume_pos

                    # 选择文件打开模式
                    file_mode = "ab" if resume_pos > 0 else "wb"

                    async with aiofiles.open(save_path, file_mode) as f:
                        async for chunk in r.aiter_bytes(chunk_size=chunk_size):
                            if chunk:  # 过滤空块
                                await f.write(chunk)
                                current += len(chunk)
                                if progress:
                                    await progress(current, total_size, *progress_args)

                    # 下载成功，退出重试循环
                    return str(save_path)

            except (
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ) as e:
                if attempt == max_retries:
                    raise DownloadError(f"连接超时: {e}") from e
                await asyncio.sleep(2**attempt)  # 指数退避
                continue

            except (
                httpx.ConnectError,
                httpx.RemoteProtocolError,
                httpx.ReadError,
            ) as e:
                if attempt == max_retries:
                    raise DownloadError(f"网络连接错误: {e}") from e
                # 更新断点续传位置
                if save_path.exists():
                    resume_pos = save_path.stat().st_size
                await asyncio.sleep(2**attempt)  # 指数退避
                continue

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (
                    416,
                    404,
                ):  # Range Not Satisfiable 或 Not Found
                    # 如果不支持断点续传，删除部分文件重新下载
                    if save_path.exists():
                        save_path.unlink()
                    resume_pos = 0
                    if attempt == max_retries:
                        raise DownloadError(f"HTTP错误: {e.response.status_code}") from e
                    continue
                else:
                    raise DownloadError(f"HTTP错误: {e.response.status_code}") from e

            except Exception as e:
                if attempt == max_retries:
                    raise DownloadError(f"下载失败: {e}") from e
                # 更新断点续传位置
                if save_path.exists():
                    resume_pos = save_path.stat().st_size
                await asyncio.sleep(2**attempt)  # 指数退避
                continue

        raise DownloadError("达到最大重试次数，下载失败")


async def get_filename_by_url(url: str, client: httpx.AsyncClient):
    response = await client.head(url, follow_redirects=True)
    response.raise_for_status()
    if content_disposition := response.headers.get("content-disposition"):
        if filename_match := re.findall("filename=(.+)", content_disposition):
            return filename_match[0]
    return url.removesuffix("/").split("/")[-1]


class DownloadError(Exception):
    pass
