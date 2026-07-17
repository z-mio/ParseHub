<div align="center">

# 🔗 ParseHub

**Social Media Content Parser**

[![PyPI version](https://img.shields.io/pypi/v/parsehub?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/parsehub/)
[![Python](https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/z-mio/parsehub?style=social)](https://github.com/z-mio/parsehub)

A lightweight, asynchronous, ready-to-use social media parser and media downloader supporting 17+ platforms.

[简体中文](README.md) | English

[Installation](#-installation) · [Quick Start](#-quick-start) · [Advanced Usage](#-advanced-usage) · [TG Bot](https://github.com/z-mio/parse_hub_bot)

</div>

---

## ✨ Features

- 🌍 **Broad platform support** — Covers 17+ leading social media platforms worldwide.
- 🧹 **URL cleanup** — Extracts URLs from shared text and removes removable tracking parameters.
- 🎬 **Multimedia parsing** — Supports videos, image posts, GIFs, live photos, and rich-text articles.
- 📦 **Synchronous / asynchronous APIs** — Provides both `async/await` and `*_sync` invocation styles.
- 🐚 **CLI support** — A lightweight, ready-to-use command-line interface.
- 🤖 **Telegram Bot** — A Bot built on this project is available at [@ParseHuBot](https://t.me/ParsehuBot).

## 🌐 Supported Platforms

| Platform        | Video | Image Posts | Other                          |
|-----------------|:-----:|:-----------:|--------------------------------|
| **Twitter / X** |   ✅   |      ✅      | 📝 Articles                    |
| **Instagram**   |   ✅   |      ✅      |                                |
| **YouTube**     |   ✅   |             | 🎵 Music                       |
| **Facebook**    |   ✅   |             |                                |
| **Threads**     |   ✅   |      ✅      |                                |
| **Bilibili**    |   ✅   |             | 📝 Updates                     |
| **Douyin**      |   ✅   |      ✅      | ☀️ Daily posts                 |
| **TikTok**      |   ✅   |      ✅      |                                |
| **Weibo**       |   ✅   |      ✅      |                                |
| **Xiaohongshu** |   ✅   |      ✅      |                                |
| **Tieba**       |   ✅   |      ✅      |                                |
| **WeChat OA**   |       |      ✅      |                                |
| **Kuaishou**    |   ✅   |             |                                |
| **Coolapk**     |       |      ✅      |                                |
| **Pipixia**     |   ✅   |      ✅      |                                |
| **Zuiyou**      |   ✅   |      ✅      |                                |
| **Xiaoheihe**   |   ✅   |      ✅      |                                |
| **Snapchat**    |   ✅   |             |                                |
| **Zhihu**       |   ✅   |      ✅      | 🐶 Questions, columns, circles |

## 📦 Installation

### Install the CLI

```bash
uv tool install "parsehub[cli]"
ph -v
```

### Install as a Python Library

```bash
# uv
uv add parsehub

# Install the `cli` extra for complete CLI capabilities.
uv add "parsehub[cli]"
```

## 🚀 Quick Start

### CLI

#### Parse a URL or shared text

```bash
parsehub "https://example.com/post/1"

# Equivalent short command
ph "https://example.com/post/1"
```

#### Download media

```bash
ph d "https://example.com/post/1"
```

#### Common commands

| Command                                          | Description                            |
|--------------------------------------------------|----------------------------------------|
| `ph ls`                                          | List supported platforms               |
| `ph set proxy <platform> <proxy>`                | Configure parsing and download proxies |
| `ph set proxy <platform> <proxy> --for download` | Configure only the download proxy      |
| `ph set cookie <platform>`                       | Save a platform Cookie                 |
| `ph set list`                                    | List configuration                     |
| `ph set show <platform>`                         | Show a platform's configuration        |

Configuration is automatically applied by platform to subsequent parsing and downloading. You can still pass arguments
directly for a temporary override:

```bash
ph "https://example.com/post/1" --proxy http://127.0.0.1:7890
ph d "https://example.com/post/1" --parse-proxy http://127.0.0.1:7890 --cookie "key=value"
```

---

### Python API

#### Parse synchronously

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.parse_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")
print(result)

dr = result.download_sync()
print(dr)
```

#### Parse asynchronously

```python
import asyncio
from parsehub import ParseHub


async def main():
    ph = ParseHub()
    result = await ph.parse("https://tieba.baidu.com/p/9939510114")
    print(result)

    dr = await result.download()
    print(dr)


asyncio.run(main())
```

#### Download media

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.download_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")
print(result)
```

## 🔑 Advanced Usage

### Cookie authentication and proxies

For platforms that require an authenticated session, pass a Cookie. The parsing API uses `cookie` / `proxy`; the
download API uses `parse_cookie` / `parse_proxy` for parameters that apply during parsing.

The following platforms currently support Cookies:

- `Twitter / X`
- `Instagram`
- `Threads`
- `YouTube`
- `Bilibili`
- `Douyin`
- `TikTok`
- `Kuaishou`
- `Xiaohongshu`
- `Zhihu`

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.parse_sync(
    "https://example.com",
    cookie="key1=value1; key2=value2",
    proxy="http://127.0.0.1:7890",
)
```

Cookies support multiple formats:

```python
# Cookie header string
ph.parse_sync("https://example.com", cookie="key1=value1; key2=value2")

# JSON string
ph.parse_sync("https://example.com", cookie='{"key1": "value1", "key2": "value2"}')

# Dictionary
ph.parse_sync("https://example.com", cookie={"key1": "value1", "key2": "value2"})
```

---

### Download progress callback

```python
from parsehub import ParseHub
from parsehub.types import ProgressUnit


class ProgressTracker:
    async def __call__(self, current: int, total: int, unit: ProgressUnit, *args, task_name: str = "", **kwargs):
        print(f"[{task_name}] {current}/{total} ({unit})")


result = ParseHub().download_sync(
    "https://example.com",
    path="./downloads",
    callback=ProgressTracker(),
    callback_args=("extra_arg",),
    callback_kwargs={"task_name": "demo"},
)
```

Possible `unit` values:

- `bytes`: Byte progress when downloading a single file.
- `count`: File-count progress when downloading multiple files.

---

### Save `metadata.json`

```python
from parsehub import ParseHub

result = ParseHub().download_sync(
    "https://example.com",
    path="./downloads",
    save_metadata=True,
)

print(result.output_dir / "metadata.json")
```

---

### Global configuration

```python
from pathlib import Path
from parsehub.config import GlobalConfig

GlobalConfig.default_save_dir = Path("./downloads")
```

---

### Error handling

```python
from parsehub import ParseHub
from parsehub.errors import ParseError, UnknownPlatform

try:
    result = ParseHub().parse_sync("https://example.com")
except UnknownPlatform:
    print("This platform is not supported yet")
except ParseError as exc:
    print(f"Parsing failed: {exc}")
```

---

## 🤝 Contributing

Pull Requests and Issues are welcome!

- Please include the relevant URL and logs when reporting a bug.

### Development checks

Before submitting code, run at least:

```bash
ruff format && ruff check --fix && uv run mypy
uv run pytest
```

## 🤝 References

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instaloader/instaloader](https://github.com/instaloader/instaloader)
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api)
- [cv-cat/ZhihuApis](https://github.com/cv-cat/ZhihuApis)

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**If this project helps you, please consider giving it a ⭐ Star!**

</div>
