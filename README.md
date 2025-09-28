# ParseHub

**支持AI总结的社交媒体聚合解析器**  
**Social Media Aggregation Analyzer Supported by AI Summarization**

> 视频总结使用 `whisper-1` 模型

**基于该项目开发的 Tg Bot:**   
[@ParsehuBot](https://t.me/ParsehuBot) | https://github.com/z-mio/parse_hub_bot

**支持的平台:**  
`Twitter 视频|图文`  
`Instagram 视频|图文`  
`微博 视频|图文`  
`贴吧 视频|图文`  
`小红书 视频|图文`  
`Youtube 视频|音乐`  
`Facebook 视频`  
`Bilibili 视频|动态`  
`抖音|TikTok 视频|图文`  
`微信公众号 图文`  
`最右 视频|图文`  
`酷安 视频|图文`  
`皮皮虾 视频|图文`  
`快手 视频`  
`......`

## 安装

`pip install parsehub`

---

> [!IMPORTANT]
><details>
><summary>注意</summary>
>
>Linux用户在导入skia-python包时可能会遇到以下报错
>
>```bash
>libGL.so.1: cannot open shared object file: No such file or directory
>```
>
>Windows用户在缺少Microsoft Visual C++ Runtime时可能会遇到以下报错
>
>```commandline
>ImportError: DLL load failed while importing skia: The specified module could not be found.
>```
>
>## 解决方法
>
>> ubuntu用户
>
>```bash
># Ubuntu 22 安装
>apt install libgl1-mesa-glx
># Ubuntu 24 安装
>apt install libgl1 libglx-mesa0
>```
>
>> ArchLinux用户
>
>```bash
>pacman -S libgl
>```
>
>> centos用户
>
>```bash
>yum install mesa-libGL -y
>```
>
>> Windows用户
>
>下载链接[Microsoft Visual C++ 2015 Redistributable Update 3 RC](microsoft.com/en-US/download/details.aspx?id=52685)
>
>
></details>

## 使用

```python
from parsehub import ParseHub
from parsehub.config import ParseConfig, DownloadConfig
import asyncio


async def main():
    ph = ParseHub(config=ParseConfig())
    result = await ph.parse('https://twitter.com/aobuta_anime/status/1827284717848424696')
    print(result)
    sr = await result.summary(download_config=DownloadConfig())
    print(sr.content)


if __name__ == '__main__':
    asyncio.run(main())
```

## 环境变量

| 名称                        | 描述                                             | 默认值                                                                                                                                                                  |
|---------------------------|------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `PROVIDER`                | 模型提供商, 支持: `openai`                            | `openai`                                                                                                                                                             |
| `API_KEY`                 | API Key                                        |                                                                                                                                                                      |
| `BASE_URL`                | API 端点                                         | `https://api.openai.com/v1`                                                                                                                                          |
| `MODEL`                   | AI总结使用的模型                                      | `gpt-4o-mini`                                                                                                                                                        |
| `PROMPT`                  | AI总结提示词                                        | Use "Simplified Chinese" to summarize the key points of articles and video subtitles. Summarize it in one sentence at the beginning and then write out n key points. ||                       |                                                                          |                                                                                                                                                                            |
| `TRANSCRIPTIONS_PROVIDER` | 语音转文本模型提供商 支持: `openai`,`azure`,`fast_whisper` |                                                                                                                                                                      ||                       |                                                                          |                                                                                                                                                                            |
| `TRANSCRIPTIONS_BASE_URL` | 语音转文本 API端点                                    |                                                                                                                                                                      ||                       |                                                                          |                                                                                                                                                                            |
| `TRANSCRIPTIONS_API_KEY`  | 语音转文本 API密钥                                    |                                                                                                                                                                      ||                       |                                                                          |                                                                                                                                                                            |

## 关于登录

- 为什么需要登录?
    - 部分平台的内容有限制，需要登录才能查看。

**通过 Cookie 登录:**

```python
from parsehub.config import ParseConfig

pc = ParseConfig(cookie="从浏览器中获取的cookie")
```

目前支持的平台:

- `twitter`
- `instagram`
- `kuaishou`
- `bilibili`

## 参考项目

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [BalconyJH/DynRender-skia](https://github.com/BalconyJH/DynRender-skia)
- [langchain-ai/langchain](https://github.com/langchain-ai/langchain)
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instaloader/instaloader](https://github.com/instaloader/instaloader)
- [JoeanAmier/XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader)
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api)