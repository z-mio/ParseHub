<div align="center">

# 🔗 ParseHub

**社交媒体聚合解析器**

[![PyPI version](https://img.shields.io/pypi/v/parsehub?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/parsehub/)
[![Python](https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/z-mio/parsehub?style=social)](https://github.com/z-mio/parsehub)

轻量, 异步, 开箱即用的社交媒体解析与媒体下载库, 支持 17+ 平台

[安装](#-安装) · [快速开始](#-快速开始) · [高级用法](#-高级用法) · [TG Bot](https://github.com/z-mio/parse_hub_bot)

</div>

---

## ✨ 特性

- 🌍 **广泛的平台支持** — 覆盖国内外 17+ 主流社交媒体平台
- 🧹 **链接清理** — 自动提取分享文案中的链接，并清除可移除的跟踪参数
- 🎬 **多媒体解析** — 支持视频, 图文, 动图, 实况照片和富文本文章
- 📦 **同步 / 异步 API** — 同时提供 `async/await` 与 `*_sync` 调用方式
- 🐚 **CLI 支持** — 命令行原生支持，轻量开箱即用
- 🤖 **Telegram Bot** — 基于本项目的 Bot 已上线 → [@ParseHuBot](https://t.me/ParsehuBot)

## 🌐 支持平台

| 平台              | 视频 | 图文 | 其他            |
|-----------------|:--:|:--:|---------------|
| **Twitter / X** | ✅  | ✅  | 📝 文章         |
| **Instagram**   | ✅  | ✅  |               |
| **YouTube**     | ✅  |    | 🎵 音乐         |
| **Facebook**    | ✅  |    |               |
| **Threads**     | ✅  | ✅  |               |
| **Bilibili**    | ✅  |    | 📝 动态         |
| **抖音**          | ✅  | ✅  | ☀️日常          |
| **TikTok**      | ✅  | ✅  |               |
| **微博**          | ✅  | ✅  |               |
| **小红书**         | ✅  | ✅  |               |
| **贴吧**          | ✅  | ✅  |               |
| **微信公众号**       |    | ✅  |               |
| **快手**          | ✅  |    |               |
| **酷安**          |    | ✅  |               |
| **皮皮虾**         | ✅  | ✅  |               |
| **最右**          | ✅  | ✅  |               |
| **小黑盒**         | ✅  | ✅  |               |
| **Snapchat**    | ✅  |    |               |
| **知乎**          | ✅  | ✅  | 🐶 问答, 专栏, 圈子 |

## 📦 安装

### CLI 安装

```bash
uv tool install "parsehub[cli]"
ph -v
```

### Python 库安装

```bash
# uv
uv add parsehub

# 需要完整 CLI 能力时，可安装 `cli` 扩展
uv add "parsehub[cli]"
```

## 🚀 快速开始

### CLI

#### 解析链接或分享文案

```bash
parsehub "https://example.com/post/1"

# 短命令等价写法
ph "https://example.com/post/1"
```

#### 下载媒体

```bash
ph d "https://example.com/post/1"
```

#### 常用命令

| 命令                                               | 说明          |
|--------------------------------------------------|-------------|
| `ph ls`                                          | 查看支持的平台     |
| `ph set proxy <platform> <proxy>`                | 设置解析代理和下载代理 |
| `ph set proxy <platform> <proxy> --for download` | 只设置下载代理     |
| `ph set cookie <platform>`                       | 保存平台 Cookie |
| `ph set list`                                    | 查看配置列表      |
| `ph set show <platform>`                         | 查看平台配置      |

配置会自动按平台应用到后续解析和下载; 临时覆盖时仍可直接传参数:

```bash
ph "https://example.com/post/1" --proxy http://127.0.0.1:7890
ph d "https://example.com/post/1" --parse-proxy http://127.0.0.1:7890 --cookie "key=value"
```

---

### Python API

#### 同步解析

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.parse_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")
print(result)

dr = result.download_sync()
print(dr)

```

#### 异步解析

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

#### 下载媒体

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.download_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")
print(result)
```

## 🔑 高级用法

### Cookie 登录与代理

需要登录态的平台可传 Cookie, 解析入口使用 `cookie` / `proxy`, 下载入口使用 `parse_cookie` / `parse_proxy` 作为解析阶段参数

当前支持 Cookie 的平台:

- `Twitter / X`
- `Instagram`
- `YouTube`
- `Bilibili`
- `抖音`
- `TikTok`
- `快手`
- `小红书`
- `知乎`

```python
from parsehub import ParseHub

ph = ParseHub()
result = ph.parse_sync(
    "https://example.com",
    cookie="key1=value1; key2=value2",
    proxy="http://127.0.0.1:7890",
)
```

Cookie 支持多种格式:

```python
# Cookie header 字符串
ph.parse_sync("https://example.com", cookie="key1=value1; key2=value2")

# JSON 字符串
ph.parse_sync("https://example.com", cookie='{"key1": "value1", "key2": "value2"}')

# 字典
ph.parse_sync("https://example.com", cookie={"key1": "value1", "key2": "value2"})
```

---

### 下载进度回调

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

`unit` 值:

- `bytes`: 单文件下载时的字节进度
- `count`: 多文件下载时的文件数量进度

---

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

---

### 全局配置

```python
from pathlib import Path
from parsehub.config import GlobalConfig

GlobalConfig.default_save_dir = Path("./downloads")
```

---

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

---

## 🤝 参与贡献

欢迎提交 Pull Request 或 Issue!

- Bug 反馈请附上相关 URL 和日志信息

### 开发规范

提交代码前请至少执行:

```bash
ruff format && ruff check --fix && uv run mypy
uv run pytest
```

## 🤝 参考项目

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instaloader/instaloader](https://github.com/instaloader/instaloader)
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api)
- [cv-cat/ZhihuApis](https://github.com/cv-cat/ZhihuApis)

## 📜 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**如果这个项目对你有帮助，欢迎点个 ⭐ Star!**

</div>
