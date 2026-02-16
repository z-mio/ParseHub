from urllib.parse import urlparse, urlunparse

from ...provider_api.twitter import (
    Twitter,
    TwitterAni,
    TwitterPhoto,
    TwitterTweet,
    TwitterVideo,
)
from ...types import AniRef, ImageRef, MultimediaParseResult, ParseError, Platform, VideoRef
from ...utils.util import cookie_ellipsis
from ..base.base import BaseParser


class TwitterParser(BaseParser):
    __platform__ = Platform.TWITTER
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?.+(twitter|x).com/.*/status/\d+"

    async def _do_parse(self, raw_url: str) -> "MultimediaParseResult":
        tweet = await self._parse(raw_url)
        return await self.media_parse(raw_url, tweet)

    async def get_raw_url(self, url: str) -> str:
        url = await super().get_raw_url(url)
        return str(urlunparse(urlparse(url)._replace(netloc="x.com")))

    async def _parse(self, url: str):
        x = Twitter(self.cfg.proxy, cookie=None)
        try:
            tweet = await x.fetch_tweet(url)
        except Exception as e:
            if any(s in str(e) for s in ("error -2",)):
                if self.cfg.cookie:
                    x2 = Twitter(self.cfg.proxy, cookie=self.cfg.cookie)
                    try:
                        tweet = await x2.fetch_tweet(url)
                    except Exception as e2:
                        raise ParseError(
                            f"Twitter 账号可能已被封禁\n\n使用的Cookie: {cookie_ellipsis(self.cfg.cookie)}"
                        ) from e2
                else:
                    raise ParseError(e) from e
            else:
                raise ParseError(e) from e
        return tweet

    @staticmethod
    async def media_parse(url, tweet: TwitterTweet):
        media = []
        for m in tweet.media:
            match m:
                case TwitterPhoto():
                    path = ImageRef(url=m.url)
                case TwitterVideo():
                    path = VideoRef(url=m.url, height=m.height, width=m.width)
                case TwitterAni():
                    path = AniRef(url=m.url, ext="mp4")
            media.append(path)
        return MultimediaParseResult(content=tweet.full_text, media=media, raw_url=url)


__all__ = ["TwitterParser"]
