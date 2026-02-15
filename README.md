# ParseHub

**一个社交媒体解析器, 支持多个平台**  
**A social media parser that supports multiple platforms**

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
`Threads 视频|图文`  
`......`

## 安装

`pip install parsehub`  

`uv add parsehub`


## 使用

```python
from parsehub import ParseHub
import asyncio


async def main():
    ph = ParseHub()
    result = await ph.parse('https://twitter.com/aobuta_anime/status/1827284717848424696')
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
```

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
- `youtube`

## 参考项目

- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [BalconyJH/DynRender-skia](https://github.com/BalconyJH/DynRender-skia)
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instaloader/instaloader](https://github.com/instaloader/instaloader)
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api)