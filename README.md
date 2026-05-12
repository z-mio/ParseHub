<div align="center">

# 🔗 ParseHub

**社交媒体聚合解析器**

[![PyPI version](https://img.shields.io/pypi/v/parsehub?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/parsehub/)
[![Python](https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/z-mio/parsehub?style=social)](https://github.com/z-mio/parsehub)

轻量、异步、开箱即用的社交媒体解析与媒体下载库，支持 17+ 平台。

[安装](#-安装) · [CLI 快速使用](#-cli-快速使用) · [Python API](#-python-api-快速使用) · [支持平台](#-支持平台) · [高级用法](#-高级用法) · [TG Bot](https://github.com/z-mio/parse_hub_bot)

</div>

---

## ✨ 特性

- 🌍 **广泛的平台支持** — 覆盖国内外 17+ 主流社交媒体平台
- 🧹 **链接清理** — 自动提取分享文案中的链接，并清除可移除的跟踪参数
- 🎬 **多媒体解析** — 支持视频、图文、动图、实况照片和富文本文章
- 📦 **同步 / 异步 API** — 同时提供 `async/await` 与 `*_sync` 调用方式
- 🤖 **Telegram Bot** — 基于本项目的 Bot 已上线 → [@ParseHuBot](https://t.me/ParsehuBot)

## 📦 安装

> Python ≥ 3.12

### 安装为命令行工具

如果主要把 ParseHub 当作 CLI 使用，推荐用 `pipx` 安装隔离的命令行环境：

```bash
pipx install "parsehub[cli]"
ph --help
```

### 安装为 Python 库

如果要在项目代码中调用 Python API：

```bash
# uv
uv add parsehub

# pip
pip install parsehub
```

项目内也需要完整 CLI 配置能力时，可安装 `cli` 扩展：

```bash
# uv
uv add "parsehub[cli]"

# pip
pip install "parsehub[cli]"
```

## 🚀 CLI 快速使用

解析链接或分享文案：

```bash
parsehub "https://example.com/post/1"

# 短命令等价写法
ph "https://example.com/post/1"
```

下载媒体：

```bash
parsehub download "https://example.com/post/1" -o ./downloads

# 短命令等价写法
ph d "https://example.com/post/1" -o ./downloads
```

查看支持的平台：

```bash
ph platforms
# 或
ph ls
```

配置某个平台的代理和 Cookie：

```bash
# 同时设置解析代理和下载代理
ph set proxy xhs http://127.0.0.1:7890

# 只设置下载代理
ph set proxy xhs http://127.0.0.1:7891 --for download

# 保存 Cookie，输入时不会显示在终端里
ph set cookie xhs

# 查看配置状态
ph set list
ph set show xhs
```

配置会自动按平台应用到后续解析和下载；临时覆盖时仍可直接传参数：

```bash
ph "https://example.com/post/1" --proxy http://127.0.0.1:7890
ph d "https://example.com/post/1" --parse-proxy http://127.0.0.1:7890 --cookie "key=value"
```

## 🐍 Python API 快速使用

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

> 可通过 `ph ls` 或 `ParseHub().get_platforms()` 获取当前版本实际注册的平台列表。

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
