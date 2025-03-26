# ParseHub

**支持AI总结的社交媒体聚合解析器**  
**Social Media Aggregation Analyzer Supported by AI Summarization**

> 视频总结使用 `whisper-1` 模型

**基于该项目开发的 Tg Bot:**   
[@ParsehubBot](https://t.me/ParsehubBot) | https://github.com/z-mio/parse_hub_bot

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

    # dr = await result.download()
    # print(dr.media)
    # sr = await dr.summary()
    # await dr.delete()

    sr = await result.summary(download_config=DownloadConfig())
    print(sr.content)


if __name__ == '__main__':
    asyncio.run(main())
```

## 环境变量

| 名称                      | 描述                                             | 默认值                                                                                                                                                                        |
|-------------------------|------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| PROVIDER                | 模型提供商, 支持: `openai`                            | openai                                                                                                                                                                     |
| API_KEY                 | API Key                                        |                                                                                                                                                                            |
| BASE_URL                | API 地址                                         | https://api.openai.com/v1                                                                                                                                                  |
| MODEL                   | AI总结使用的模型                                      | gpt-4o-mini                                                                                                                                                                |
| PROMPT                  | AI总结提示词                                        | You are a useful assistant to summarize the main points of articles and video captions. Summarize 3 to 8 points in "Simplified Chinese" and summarize them all at the end. ||                       |                                                                          |                                                                                                                                                                            |
| TRANSCRIPTIONS_PROVIDER | 语音转文本模型提供商 支持: `openai`,`azure`,`fast_whisper` | openai                                                                                                                                                                     ||                       |                                                                          |                                                                                                                                                                            |
| AZURE_SPEECH_REGION     | 语音转文本 azure端点                                  |                                                                                                                                                                            ||                       |                                                                          |                                                                                                                                                                            |
| AZURE_SPEECH_KEY        | 语音转文本 azure密钥                                  |                                                                                                                                                                            ||                       |                                                                          |                                                                                                                                                                            |

## 参考项目

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [BalconyJH/DynRender-skia](https://github.com/BalconyJH/DynRender-skia)
- [langchain-ai/langchain](https://github.com/langchain-ai/langchain)
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instaloader/instaloader](https://github.com/instaloader/instaloader)
- [JoeanAmier/XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader)