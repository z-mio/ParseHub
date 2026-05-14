from dataclasses import dataclass

import httpx

from .. import ParseError
from ..config.config import GlobalConfig


class KuaiShouAPI:
    def __init__(
        self,
        cookie: dict,
        proxy: str = None,
    ):
        self.api_url = "https://www.kuaishou.com/graphql"
        self.proxy = proxy
        self.cookie = cookie
        self.headers = {
            "User-Agent": GlobalConfig.ua,
            "content-type": "application/json",
        }

    async def get_video_info(self, url: str) -> "KuaiShouVideo":
        body = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": self.get_video_id(url), "page": "search"},
            "query": """query visionVideoDetail($photoId: String, $type: String, $page: String, $webPageArea: String) {
          visionVideoDetail(photoId: $photoId, type: $type, page: $page, webPageArea: $webPageArea) {
            status
            type
            author {
              id
              name
              following
              headerUrl
              __typename
            }
            photo {
              id
              duration
              caption
              likeCount
              realLikeCount
              coverUrl
              photoUrl
              liked
              timestamp
              expTag
              llsid
              viewCount
              videoRatio
              stereoType
              musicBlocked
              manifest {
                mediaType
                businessType
                version
                adaptationSet {
                  id
                  duration
                  representation {
                    id
                    defaultSelect
                    backupUrl
                    codecs
                    url
                    height
                    width
                    avgBitrate
                    maxBitrate
                    m3u8Slice
                    qualityType
                    qualityLabel
                    frameRate
                    featureP2sp
                    hidden
                    disableAdaptive
                    __typename
                  }
                  __typename
                }
                __typename
              }
              manifestH265
              photoH265Url
              coronaCropManifest
              coronaCropManifestH265
              croppedPhotoH265Url
              croppedPhotoUrl
              videoResource
              __typename
            }
            tags {
              type
              name
              __typename
            }
            commentLimit {
              canAddComment
              __typename
            }
            llsid
            danmakuSwitch
            __typename
          }
        }
        """,
        }
        async with httpx.AsyncClient(proxy=self.proxy, headers=self.headers, cookies=self.cookie) as client:
            response = await client.post(self.api_url, json=body)
            response.raise_for_status()
            raw_data = response.json()
            if not (data := raw_data.get("data")):
                raise Exception("did 未填")
            if err := raw_data.get("errors"):
                match err[0]["message"]:
                    case "Need captcha":
                        raise Exception("-1 账号风控, 需要验证")
            elif err_code := data.get("result"):
                match err_code:
                    case 400002:
                        raise Exception("400002 账号风控, 需要验证")

            return KuaiShouVideo.parse(data)

    @staticmethod
    def get_video_id(url: str):
        if "/photo/" in url:
            raise ValueError("暂不支持图文解析")
        return url.split("/")[-1]


@dataclass
class KuaiShouVideo:
    title: str
    video_url: str
    thumb_url: str
    duration: int
    height: int
    width: int

    @classmethod
    def parse(cls, data: dict):
        vision_video_detail = data.get("visionVideoDetail", {})
        photo = vision_video_detail.get("photo")
        if not photo:
            raise Exception("-2 账号风控")
        vi = cls._get_video(photo)
        return cls(
            title=photo.get("caption"),
            video_url=vi["url"],
            thumb_url=photo.get("coverUrl"),
            duration=vi["duration"],
            height=vi["height"],
            width=vi["width"],
        )

    @staticmethod
    def _get_video(photo: dict) -> dict:
        if not (vr := photo.get("manifestH265")):
            vr = photo.get("videoResource", {}).get("h264")
        if not vr:
            raise ParseError("未提取到视频信息")

        adaptation_set = (vr.get("adaptationSet") or [{}])[0]
        representation = (adaptation_set.get("representation") or [{}])[0]

        return {
            "url": representation.get("url"),
            "width": representation.get("width"),
            "height": representation.get("height"),
            "duration": adaptation_set.get("duration"),
        }
