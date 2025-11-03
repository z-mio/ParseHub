from ...provider_api.threads import ThreadsAPI, ThreadsMediaType
from ...types import Image, MultimediaParseResult, Video
from ..base.base import BaseParser


class ThreadsParser(BaseParser):
    __platform_id__ = "threads"
    __platform__ = "Threads"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+threads.com/@\w+/post/.*"

    async def parse(self, url: str) -> "MultimediaParseResult":
        url = await self.get_raw_url(url)
        post = await ThreadsAPI(proxy=self.cfg.proxy).parse(url)
        media = []
        if post.media:
            pm = post.media if isinstance(post.media, list) else [post.media]
            for m in pm:
                match m.type:
                    case ThreadsMediaType.VIDEO:
                        media.append(Video(path=m.url, thumb_url=m.thumb_url, width=m.width, height=m.height))
                    case ThreadsMediaType.IMAGE:
                        media.append(Image(path=m.url, thumb_url=m.url, width=m.width, height=m.height))
        return MultimediaParseResult(desc=post.content, media=media, raw_url=url)


__all__ = ["ThreadsParser"]
