<div align="center">

# 🔗 ParseHub

**社交媒体聚合解析器**

[![PyPI version](https://img.shields.io/pypi/v/parsehub?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/parsehub/)
[![Python](https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/z-mio/parsehub?style=social)](https://github.com/z-mio/parsehub)

轻量、异步、开箱即用的社交媒体解析与媒体下载库，支持 17+ 平台。

[支持平台](#-支持平台) · [安装](#-安装) · [快速开始](#-快速开始) · [API](#-api-速览) · [高级用法](#-高级用法) · [TG Bot](https://github.com/z-mio/parse_hub_bot)

</div>

---

## ✨ 特性

- 🌍 **广泛的平台支持** — 覆盖国内外 17+ 主流社交媒体平台
- 🧹 **链接清理** — 自动提取分享文案中的链接，并清除可移除的跟踪参数
- 🎬 **多媒体解析** — 支持视频、图文、动图、实况照片和富文本文章
- 📦 **同步 / 异步 API** — 同时提供 `async/await` 与 `*_sync` 调用方式
- 🤖 **Telegram Bot** — 基于本项目的 Bot 已上线 → [@ParseHuBot](https://t.me/ParsehuBot)

## 🌐 支持平台

| 平台              | 视频 | 图文 | 其他    |
|:----------------|:--:|:--:|:------|
| **Twitter / X** | ✅  | ✅  |       |
| **Instagram**   | ✅  | ✅  |       |
| **YouTube**     | ✅  |    | 🎵 音乐 |
| **Facebook**    | ✅  |    |       |
| **Threads**     | ✅  | ✅  |       |
| **Bilibili**    | ✅  |    | 📝 动态 |
| **抖音**          | ✅  | ✅  |       |
| **TikTok**      | ✅  | ✅  |       |
| **微博**          | ✅  | ✅  |       |
| **小红书**         | ✅  | ✅  |       |
| **贴吧**          | ✅  | ✅  |       |
| **微信公众号**       |    | ✅  |       |
| **快手**          | ✅  |    |       |
| **酷安**          |    | ✅  |       |
| **皮皮虾**         | ✅  | ✅  |       |
| **最右**          | ✅  | ✅  |       |
| **小黑盒**         | ✅  | ✅  |       |

> 可通过 `ParseHub().get_platforms()` 获取当前版本实际注册的平台列表。

## 📦 安装

```bash
# uv (推荐)
uv add parsehub

# pip
pip install parsehub
```

> 要求 Python ≥ 3.12

## 🚀 快速开始

### 同步解析

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.parse_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")

print(result.title)
print(result.raw_url)
```

### 异步解析

```python
import asyncio
from parsehub import ParseHub


async def main():
    ph = ParseHub()
    result = await ph.parse("https://tieba.baidu.com/p/9939510114")
    print(result)


asyncio.run(main())
```

### 下载媒体

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.download_sync(
    "https://www.xiaoheihe.cn/app/bbs/link/174972336",
    path="./downloads",
    save_metadata=True,
)

print(result.output_dir)
print(result.media)
```

需要 Cookie 登录或解析代理时，可以直接在下载时传入解析参数：

```python
from parsehub import ParseHub

ph = ParseHub()
downloaded = ph.download_sync(
    "https://example.com",
    path="./downloads",
    parse_cookie="key1=value1; key2=value2",
    parse_proxy="http://127.0.0.1:7890",
    save_metadata=True,
)
```

## 🧩 API 速览

### 解析

```python
await ph.parse(url, proxy=None, cookie=None)
ph.parse_sync(url, proxy=None, cookie=None)
```

- `url`：分享文案或分享链接，支持自动提取文本中的第一个链接
- `proxy`：解析阶段使用的代理
- `cookie`：解析阶段使用的 Cookie，支持字符串、JSON 字符串或字典

### 下载

```python
await ph.download(
    url,
    path=None,
    callback=None,
    callback_args=(),
    callback_kwargs=None,
    proxy=None,
    parse_proxy=None,
    parse_cookie=None,
    save_metadata=False,
)

ph.download_sync(
    url,
    path=None,
    callback=None,
    callback_args=(),
    callback_kwargs=None,
    proxy=None,
    parse_proxy=None,
    parse_cookie=None,
    save_metadata=False,
)
```

- `path`：下载保存目录，默认使用 `GlobalConfig.default_save_dir`
- `proxy`：下载媒体时使用的代理
- `parse_proxy` / `parse_cookie`：下载前解析链接时使用的代理和 Cookie
- `save_metadata`：是否在输出目录保存 `metadata.json`

### 工具方法

```python
ph.get_platform(url)
ph.get_platforms()
await ph.get_raw_url(url, proxy=None, clean_all=True)
```

- `get_platform()`：返回匹配到的平台枚举，未匹配时返回 `None`
- `get_platforms()`：返回所有已注册平台的 `id`、名称和支持类型
- `get_raw_url()`：获取清理后的原始链接

### 解析结果

- `result.platform`：平台枚举
- `result.type`：内容类型，如 `video`、`image`、`multimedia`、`richtext`
- `result.title`：标题
- `result.content`：纯文本正文
- `result.raw_url`：清理后的原始链接
- `result.media`：媒体引用或媒体引用列表
- `result.to_dict()`：转为可序列化字典
- `result.download()` / `result.download_sync()`：下载当前解析结果中的媒体

## 🔑 高级用法

### 分享文案与平台识别

`url` 参数可以直接传分享文案，ParseHub 会自动提取其中的第一个链接：

```python
from parsehub import ParseHub

ph = ParseHub()
text = "复制这条分享 https://tieba.baidu.com/p/9939510114 后打开"

print(ph.get_platform(text))
print(ph.parse_sync(text).raw_url)
```

### Cookie 登录与代理

需要登录态的平台可传 Cookie；解析入口使用 `cookie` / `proxy`，下载入口使用 `parse_cookie` / `parse_proxy` 作为解析阶段参数。

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.parse_sync(
    "https://example.com",
    cookie="key1=value1; key2=value2",
    proxy="http://127.0.0.1:7890",
)
```

Cookie 支持多种格式：

```python
from parsehub import ParseHub

ph = ParseHub()

# Cookie header 字符串
ph.parse_sync("https://example.com", cookie="key1=value1; key2=value2")

# JSON 字符串
ph.parse_sync("https://example.com", cookie='{"key1": "value1", "key2": "value2"}')

# 字典
ph.parse_sync("https://example.com", cookie={"key1": "value1", "key2": "value2"})
```

当前支持 Cookie 的平台包括：

- `Twitter / X`
- `Instagram`
- `YouTube`
- `Bilibili`
- `抖音`
- `TikTok`
- `快手`

### 下载进度回调

```python
from parsehub import ParseHub


class ProgressTracker:
    async def __call__(self, current: int, total: int, unit: str, *args, task_name: str = "", **kwargs):
        print(f"[{task_name}] {current}/{total} ({unit})")


result = ParseHub().download_sync(
    "https://example.com",
    path="./downloads",
    callback=ProgressTracker(),
    callback_args=("extra_arg",),
    callback_kwargs={"task_name": "demo"},
)
```

`unit` 可能为：

- `bytes`：单文件下载时的字节进度
- `count`：多文件下载时的文件数量进度

### 保存 metadata.json

```python
from parsehub import ParseHub

result = ParseHub().download_sync(
    "https://example.com",
    path="./downloads",
    save_metadata=True,
)

print(result.output_dir / "metadata.json")
```

### 全局配置

```python
from pathlib import Path
from parsehub.config import GlobalConfig

GlobalConfig.default_save_dir = Path("./downloads")
```

### 错误处理

```python
from parsehub import ParseHub
from parsehub.errors import ParseError, UnknownPlatform

try:
    result = ParseHub().parse_sync("https://example.com")
except UnknownPlatform:
    print("暂不支持该平台")
except ParseError as exc:
    print(f"解析失败: {exc}")
```

## 🤝 参考项目

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instaloader/instaloader](https://github.com/instaloader/instaloader)
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api)

## 📜 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**如果这个项目对你有帮助，欢迎点个 ⭐ Star！**

</div>
