from ...provider_api.threads import ThreadsAPI, ThreadsMedia, ThreadsMediaType
from ...types import ImageRef, MultimediaParseResult, VideoRef
from ...types.platform import Platform
from ..base.base import BaseParser


class ThreadsParser(BaseParser):
    __platform__ = Platform.THREADS
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+threads.com/@[\w.]+/post/.*"

    async def _do_parse(self, raw_url: str) -> "MultimediaParseResult":
        post = await ThreadsAPI(proxy=self.cfg.proxy).parse(raw_url)
        media = []
        if post.media:
            pm: list[ThreadsMedia] = post.media if isinstance(post.media, list) else [post.media]
            for m in pm:
                match m.type:
                    case ThreadsMediaType.VIDEO:
                        media.append(VideoRef(url=m.url, thumb_url=m.thumb_url, width=m.width, height=m.height))
                    case ThreadsMediaType.IMAGE:
                        media.append(ImageRef(url=m.url, thumb_url=m.url, width=m.width, height=m.height))
        return MultimediaParseResult(content=post.content, media=media, raw_url=raw_url)


__all__ = ["ThreadsParser"]
