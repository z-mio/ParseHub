from dataclasses import dataclass

import httpx

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
        data = {
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
            response = await client.post(self.api_url, json=data)
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                raise Exception("did 未填")

            if err := data.get("errors"):
                match err[0]["message"]:
                    case "Need captcha":
                        raise Exception("-1 账号风控")

            return KuaiShouVideo.parse(data["data"])

    @staticmethod
    def get_video_id(url: str):
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
        vision_video_detail = data.get("visionVideoDetail")
        photo = vision_video_detail.get("photo")
        if not photo:
            raise Exception("-2 账号风控")
        manifest_h265 = photo.get("manifestH265")
        adaptation_set = manifest_h265["adaptationSet"][0]
        representation = adaptation_set.get("representation")[0]
        return cls(
            title=photo.get("caption"),
            video_url=representation.get("url"),
            thumb_url=photo.get("coverUrl"),
            duration=adaptation_set.get("duration"),
            height=representation.get("height"),
            width=representation.get("width"),
        )
