import abc
import asyncio
import re
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from inspect import signature
from typing import Any
from urllib.parse import urlparse

import httpx


class WeiboAPI:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def resolve_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.hostname != "mapp.api.weibo.cn" or not parsed.path.startswith("/fx/"):
            return url

        async with httpx.AsyncClient(proxy=self.proxy, follow_redirects=False, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.headers.get("location") or url

    async def get_id_by_url(self, url: str) -> str | None:
        url = await self.resolve_url(url)
        parsed = urlparse(url)
        if match := re.compile(r"^/status/([^/?#]+)").match(parsed.path):
            return match[1]

        bid = url.split("/")[-1]
        if bid.isdigit() or len(bid) == 9:
            return bid
        return None

    async def parse(self, url: str) -> "WeiboContent":
        bid = await self.get_id_by_url(url)
        if not bid:
            raise ValueError("Invalid URL")
        headers = {
            "referer": "https://weibo.com",
        }
        cookies = {
            "SUB": "_2AkMR47Mlf8NxqwFRmfocxG_lbox2wg7EieKnv0L-JRMxHRl-yT9yqhFdtRB6OmOdyoia9pKPkqoHRRmSBA_WNPaHuybH",
        }
        api = f"https://weibo.com/ajax/statuses/show?id={bid}&isGetLongText=true"
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.get(api, cookies=cookies, headers=headers)
            response.raise_for_status()
            result = response.json()
        return WeiboContent.parse(result)


class MediaType(Enum):
    VIDEO = "video"
    PHOTO = "pic"
    LIVE_PHOTO = "livephoto"
    GIF = "gif"


class Info(abc.ABC):
    @property
    @abstractmethod
    def media_url(self) -> str | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def thumb_url(self) -> str | None:
        raise NotImplementedError()


@dataclass
class Playback:
    url: str
    width: int = 0
    height: int = 0
    duration: float = 0
    bitrate: int = 0
    size: int = 0

    @classmethod
    def parse(cls, playback: dict) -> "Playback":
        pi = playback["play_info"]
        url = pi["url"]
        width = pi["width"]
        height = pi["height"]
        duration = pi.get("duration", 0)
        bitrate = pi.get("bitrate", 0)
        size = pi.get("size", 0)
        return cls(url, width, height, duration, bitrate, size)


@dataclass
class MediaInfo:
    format: str | None = None
    mp4_hd_url: str | None = None
    mp4_sd_url: str | None = None
    duration: int = 0
    prefetch_size: int | None = None
    playback: Playback | None = None

    @staticmethod
    def parse(media_dict: dict) -> "MediaInfo":
        format_ = media_dict["format"]
        mp4_hd_url = media_dict.get("mp4_hd_url")
        mp4_sd_url = media_dict.get("mp4_sd_url")
        duration = media_dict["duration"]
        prefetch_size = media_dict["prefetch_size"]
        playback_list = media_dict.get("playback_list", [])
        playback = Playback.parse(playback_list[0]) if playback_list else None
        return MediaInfo(format_, mp4_hd_url, mp4_sd_url, duration, prefetch_size, playback)


@dataclass
class PageInfo(Info):
    object_type: MediaType | None = None
    media_info: MediaInfo | None = None
    page_pic: str | None = None
    short_url: str | None = None

    @staticmethod
    def parse(page_info_dict: dict) -> "PageInfo":
        object_type = MediaType(page_info_dict["object_type"])
        media_info = MediaInfo.parse(page_info_dict["media_info"])
        page_pic = page_info_dict.get("page_pic")
        short_url = page_info_dict.get("short_url")
        return PageInfo(object_type, media_info, page_pic, short_url)

    @property
    def media_url(self) -> str | None:
        if self.media_info and self.media_info.playback:
            return self.media_info.playback.url
        if self.media_info:
            return self.media_info.mp4_hd_url or self.media_info.mp4_sd_url
        return None

    @property
    def thumb_url(self) -> str | None:
        return self.page_pic

    @property
    def height(self) -> int:
        if self.media_info and self.media_info.playback:
            return self.media_info.playback.height
        return 0

    @property
    def width(self) -> int:
        if self.media_info and self.media_info.playback:
            return self.media_info.playback.width
        return 0

    @property
    def duration(self) -> int:
        return self.media_info.duration if self.media_info else 0


@dataclass
class Pic:
    url: str | None = None
    width: int | None = None
    height: int | None = None
    cut_type: int | None = None
    type: str | None = None


@dataclass
class PicInfo(Info):
    """photo, livephoto, gif.
    video为livephoto和gif视频
    """

    pic_id: str | None = None
    type: MediaType | None = None
    thumbnail: Pic | None = None
    largest: Pic | None = None
    video: str | None = None

    @staticmethod
    def parse(pic_dict: dict) -> "PicInfo":
        return PicInfo(
            pic_id=pic_dict["pic_id"],
            type=MediaType(pic_dict["type"]),
            thumbnail=Pic(**pic_dict["thumbnail"]),
            largest=Pic(**pic_dict["largest"]),
            video=pic_dict.get("video_hd") or pic_dict.get("video"),
        )

    @property
    def media_url(self) -> str | None:
        return self.largest.url if self.type == MediaType.PHOTO and self.largest else self.video

    @property
    def thumb_url(self) -> str | None:
        return self.thumbnail.url if self.thumbnail else None

    @property
    def height(self) -> int:
        return self.largest.height if self.largest and self.largest.height is not None else 0

    @property
    def width(self) -> int:
        return self.largest.width if self.largest and self.largest.width is not None else 0

    @property
    def duration(self) -> int:
        return 0


@dataclass
class MixMediaInfoItem(Info):
    type: MediaType | None = None
    data: PageInfo | PicInfo | None = None

    @property
    def media_url(self) -> str | None:
        return self.data.media_url if self.data else None

    @property
    def thumb_url(self) -> str | None:
        return self.data.thumb_url if self.data else None

    @property
    def height(self) -> int:
        return self.data.height if self.data else 0

    @property
    def width(self) -> int:
        return self.data.width if self.data else 0

    @property
    def duration(self) -> int:
        return self.data.duration if self.data else 0


@dataclass
class MixMediaInfo:
    items: list[MixMediaInfoItem] | None = None

    @staticmethod
    def parse(mix_media_info_dict: dict) -> "MixMediaInfo":
        items: list[MixMediaInfoItem] = []
        for item_dict in mix_media_info_dict["items"]:
            type_ = MediaType(item_dict["type"])
            data: PageInfo | PicInfo | None
            if type_ == MediaType.PHOTO:
                data = PicInfo.parse(item_dict["data"])
            elif type_ == MediaType.VIDEO:
                data = PageInfo.parse(item_dict["data"])
            else:
                data = None
            items.append(MixMediaInfoItem(type_, data))
        return MixMediaInfo(items)


@dataclass
class Data:
    id: str | None = None
    mid: str | None = None
    text: str | None = None  # 带html标签
    text_raw: str | None = None  # 纯文本
    pic_infos: list[PicInfo] | None = None
    page_info: PageInfo | None = None
    mix_media_info: MixMediaInfo | None = None
    retweeted_status: "Data | None" = None

    @staticmethod
    def parse(data_dict: dict) -> "Data":
        if page_info := data_dict.get("page_info"):
            data_dict["page_info"] = PageInfo.parse(page_info)
        if pic_infos := data_dict.get("pic_infos"):
            data_dict["pic_infos"] = [PicInfo.parse(pic_info) for pic_info in pic_infos.values()]
        if mix_media_info := data_dict.get("mix_media_info"):
            data_dict["mix_media_info"] = MixMediaInfo.parse(mix_media_info)
        if retweeted_status := data_dict.get("retweeted_status"):
            data_dict["retweeted_status"] = Data.parse(retweeted_status)
        return Data.from_kwargs(**data_dict)

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> "Data":
        cls_fields = set(signature(cls).parameters)

        native_args, new_args = {}, {}
        for name, val in kwargs.items():
            if name in cls_fields:
                native_args[name] = val
            else:
                new_args[name] = val

        ret = cls(**native_args)

        for new_name, new_val in new_args.items():
            setattr(ret, new_name, new_val)
        return ret

    @property
    def content(self) -> str:
        """干净的正文"""
        text = self.text_raw or ""
        if short_url := (self.page_info and self.page_info.short_url):
            text = text.replace(short_url, "")
        return text.strip()


@dataclass
class WeiboContent:
    data: Data

    @staticmethod
    def parse(json_dict: dict) -> "WeiboContent":
        data = Data.parse(json_dict)
        return WeiboContent(data=data)


if __name__ == "__main__":
    print(asyncio.run(WeiboAPI().parse("https://weibo.com/6576374129/Qv0n8sXum")))
