from typing import Union

import httpx

from ...provider_api.tieba import TieBa, TieBaError, TieBaPostType
from ...types import AniRef, ImageParseResult, ImageRef, ParseError, Platform, VideoParseResult, VideoRef
from ..base.base import BaseParser


class TieBaParser(BaseParser):
    __platform__ = Platform.TIEBA
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+tieba.baidu.com/p/\d+"

    async def _do_parse(self, raw_url: str) -> Union["ImageParseResult", "VideoParseResult"]:
        try:
            tb = await TieBa(self.proxy).parse(raw_url)
        except TieBaError as e:
            raise ParseError(e.msg if e.msg else "贴吧解析失败: 未知错误") from e
        except Exception as e:
            raise ParseError("贴吧解析失败: 未知错误") from e

        match tb.type:
            case TieBaPostType.VIDEO:
                return VideoParseResult(
                    title=tb.title,
                    video=VideoRef(
                        url=tb.media.url,
                        thumb_url=tb.media.thumb_url,
                        width=tb.media.width,
                        height=tb.media.height,
                        duration=tb.media.duration,
                    ),
                    content=tb.content,
                )

            case TieBaPostType.PHOTO:
                images = []
                if tb.media:
                    for i in tb.media:
                        async with httpx.AsyncClient(proxy=self.proxy) as cli:
                            try:
                                r = await cli.head(i.url)
                                r.raise_for_status()
                            except Exception:
                                images.append(
                                    ImageRef(
                                        url=i.url,
                                        thumb_url=i.thumb_url,
                                        width=i.width,
                                        height=i.height,
                                    )
                                )
                            else:
                                headers = r.headers
                                if (t := headers.get("content-type")) and "gif" in t:
                                    images.append(
                                        AniRef(
                                            url=i.url,
                                            thumb_url=i.thumb_url,
                                            width=i.width,
                                            height=i.height,
                                        )
                                    )
                                else:
                                    images.append(
                                        ImageRef(
                                            url=i.url,
                                            thumb_url=i.thumb_url,
                                            width=i.width,
                                            height=i.height,
                                        )
                                    )

                return ImageParseResult(title=tb.title, content=tb.content, photo=images)


__all__ = ["TieBaParser"]
