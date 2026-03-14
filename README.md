<div align="center">

# 🔗 ParseHub

**社交媒体聚合解析器**

[![PyPI version](https://img.shields.io/pypi/v/parsehub?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/parsehub/)
[![Python](https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/z-mio/parsehub?style=social)](https://github.com/z-mio/parsehub)

轻量、异步、开箱即用的社交媒体聚合解析库，支持 16+ 平台 🚀

[快速开始](#-快速开始) · [支持平台](#-支持平台) · [高级用法](#-高级用法) · [TG Bot](https://github.com/z-mio/parse_hub_bot)

</div>

---

## ✨ 特性

- 🌍 **广泛的平台支持** — 覆盖国内外 16+ 主流社交媒体
- 🧹 **隐私保护** — 自动清除链接中的跟踪参数, 返回干净的原始链接
- 🎬 **多媒体支持** — 视频 / 图文 / 动图 / 实况照片，一网打尽
- 📦 **开箱即用** — `async/await` 原生支持，API 极简
- 🤖 **Telegram Bot** — 基于本项目的 Bot 已上线 → [@ParsehuBot](https://t.me/ParsehuBot)

## 📦 安装

```bash
# pip
pip install parsehub

# uv (推荐)
uv add parsehub
```

> 要求 Python ≥ 3.12

## 🚀 快速开始

```python
from parsehub import ParseHub

result = ParseHub().parse_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")
print(result)
# ImageParseResult(platform=小黑盒, title=名为希望和绝望的红包, content=[cube_doge][cube_doge][cube_doge], media=[17], raw_url=https://www.xiaoheihe.cn/app/bbs/link/174972336)
```

### 下载媒体

```python
from parsehub import ParseHub

result = ParseHub().download_sync("https://www.xiaoheihe.cn/app/bbs/link/174972336")
print(result)
# DownloadResult(media=[ImageFile(path='D:\\downloads\\名为希望和绝望的红包\\0.jpg', width=1773, height=2364), ...], output_dir=D:\downloads\名为希望和绝望的红包)
```

## 🌐 支持平台

| 平台              | 视频 | 图文 |  其他   |
|:----------------|:--:|:--:|:-----:|
| **Twitter / X** | ✅  | ✅  |       |
| **Instagram**   | ✅  | ✅  |       |
| **YouTube**     | ✅  |    | 🎵 音乐 |
| **Facebook**    | ✅  |    |       |
| **Threads**     | ✅  | ✅  |       |
| **Bilibili**    | ✅  |    | 📝 动态 |
| **抖音 / TikTok** | ✅  | ✅  |       |
| **微博**          | ✅  | ✅  |       |
| **小红书**         | ✅  | ✅  |       |
| **贴吧**          | ✅  | ✅  |       |
| **微信公众号**       |    | ✅  |       |
| **快手**          | ✅  |    |       |
| **酷安**          | ✅  | ✅  |       |
| **皮皮虾**         | ✅  | ✅  |       |
| **最右**          | ✅  | ✅  |       |
| **小黑盒**         | ✅  | ✅  |       |

> 🔧 更多平台持续接入中...

## 🔑 高级用法

### 下载进度回调

```python
from parsehub import ParseHub


class ProgressTracker:
    async def __call__(self, current: int, total: int, unit: str, *args, task_name: str = "", **kwargs):
        print(f"[{task_name}] {current}/{total} ({unit})")


result = ParseHub().download_sync(
    "https://example.com",
    callback=ProgressTracker(),
    callback_args=("extra_arg",),
    callback_kwargs={"task_name": "demo"},
)
```

### Cookie 登录 & 代理

部分平台的内容需要登录才能访问，通过 Cookie 即可解锁：

```python
from parsehub import ParseHub

ph = ParseHub(cookie="key1=value1; key2=value2", proxy="http://127.0.0.1:7890", )
```

Cookie 支持多种格式传入：

```python
# 字符串
ParseHub(cookie="key1=value1; key2=value2")

# JSON 字符串
ParseHub(cookie='{"key1": "value1", "key2": "value2"}')

# 字典
ParseHub(cookie={"key1": "value1", "key2": "value2"})
```

目前支持 Cookie 登录的平台:

`Twitter` · `Instagram` · `Kuaishou` · `Bilibili` · `YouTube`

### 全局配置

```python
from parsehub.config import GlobalConfig

# 自定义默认下载目录
GlobalConfig.default_save_dir = "./my_downloads"
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


