# ParseHub

**支持AI总结的社交媒体聚合解析器**

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

> 视频总结会调用 `whisper-1` 模型

## 安装

`pip install parsehub`

## 使用

```python
from parsehub import ParseHub
from parsehub.config import ParseHubConfig
import asyncio


async def main():
    # ParseHubConfig.api_key = 'your_api_key'
    # ParseHubConfig.base_url = 'your_base_url'
    # ParseHubConfig.prompt = '...'

    ph = ParseHub()
    result = await ph.parse('https://twitter.com/aobuta_anime/status/1827284717848424696')
    print(result)

    # download_result = await result.download()
    # print(download_result.media)
    # summary_result = await download_result.summary()
    # await download_result.delete()

    summary_result = await result.summary()
    print(summary_result.content)


if __name__ == '__main__':
    asyncio.run(main())
```

## 环境变量

| 名称                    | 描述                                                                       | 默认值                                                                                                                                                                        |
|-----------------------|--------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| DOUYIN_API            | 抖音解析API地址, 项目地址: https://github.com/Evil0ctal/Douyin_TikTok_Download_API | https://douyin.wtf                                                                                                                                                         |
| PROVIDER              | 模型提供商, 暂只支持openai                                                        | openai                                                                                                                                                                     |
| API_KEY               | API Key                                                                  |                                                                                                                                                                            |
| BASE_URL              | API 地址                                                                   | https://api.openai.com/v1                                                                                                                                                  |
| MODEL                 | AI总结使用的模型                                                                | gpt-4o-mini                                                                                                                                                                |
| PROMPT                | AI总结提示词                                                                  | You are a useful assistant to summarize the main points of articles and video captions. Summarize 3 to 8 points in "Simplified Chinese" and summarize them all at the end. |
| YT_DLP_DURATION_LIMIT | 使用yt-dlp下载超过指定时长的视频时, 下载最低画质, 单位秒, 0为不限制                                 | 0                                                                                                                                                                          |
