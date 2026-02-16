import re

from ...provider_api.weibo import MediaType, WeiboAPI
from ...types import (
    AniRef,
    ImageParseResult,
    ImageRef,
    LivePhotoRef,
    MultimediaParseResult,
    Platform,
    VideoParseResult,
    VideoRef,
)
from ..base.base import BaseParser


class WeiboParser(BaseParser):
    __platform__ = Platform.WEIBO
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)(m\.|)weibo.(com|cn)/(?!(u/)).+"

    async def _do_parse(self, raw_url: str) -> MultimediaParseResult | VideoParseResult | ImageParseResult:
        weibo = await WeiboAPI(self.cfg.proxy).parse(raw_url)
        data = weibo.data
        text = self.f_text(data.content)
        media = []

        if not data.pic_infos and data.page_info:
            if data.page_info.object_type == MediaType.VIDEO:
                return VideoParseResult(
                    content=text,
                    raw_url=raw_url,
                    video=VideoRef(
                        url=data.page_info.media_info.playback.url,
                        thumb_url=data.page_info.page_pic,
                        width=data.page_info.media_info.playback.width,
                        height=data.page_info.media_info.playback.height,
                        duration=int(data.page_info.media_info.playback.duration),
                    ),
                )

        media_info = (
            ((rs := data.retweeted_status) and rs.pic_infos)
            or data.pic_infos
            or (data.mix_media_info and data.mix_media_info.items)
        )
        if not media_info:
            return MultimediaParseResult(content=text, raw_url=raw_url, media=[])

        for i in media_info:
            match i.type:
                case MediaType.VIDEO:
                    media.append(
                        VideoRef(
                            url=i.media_url, thumb_url=i.thumb_url, width=i.width, height=i.height, duration=i.duration
                        )
                    )
                case MediaType.LIVE_PHOTO:
                    media.append(
                        LivePhotoRef(
                            url=i.thumb_url,
                            ext="mov",
                            video_url=i.media_url,
                            width=i.width,
                            height=i.height,
                        )
                    )
                case MediaType.GIF:
                    media.append(AniRef(url=i.media_url, thumb_url=i.thumb_url))
                case _:
                    media.append(ImageRef(url=i.media_url, thumb_url=i.thumb_url, width=i.width, height=i.height))
        if all((isinstance(m, ImageRef) or isinstance(m, LivePhotoRef)) for m in media):
            return ImageParseResult(content=text, raw_url=raw_url, photo=media)
        return MultimediaParseResult(content=text, raw_url=raw_url, media=media)

    def f_text(self, text: str) -> str:
        # text = re.sub(r'<a  href="https://video.weibo.com.*?>.*的微博视频.*</a>', "", text)
        # text = re.sub(r"<[^>]+>", " ", text)
        text = self.hashtag_handler(text)
        return text.strip()

    @staticmethod
    def hashtag_handler(desc: str):
        hashtags = re.findall(r" ?#[^#]+# ?", desc)
        for hashtag in hashtags:
            desc = desc.replace(hashtag, f" {hashtag.strip().removesuffix('#')} ")
        return desc


__all__ = ["WeiboParser"]
