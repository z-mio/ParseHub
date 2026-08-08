# mypy: disable-error-code=no-untyped-def
import json
from dataclasses import dataclass
from typing import Any, Self, cast
from urllib.parse import parse_qs, urlparse

import httpx
from loguru import logger

from .. import ParseError
from ..utils.helpers import UA


class KuaiShouAPI:
    def __init__(
        self,
        cookie: dict | None,
        proxy: str | None = None,
    ):
        self.api_url = "https://www.kuaishou.com/graphql"
        self.proxy = proxy
        self.cookie = cookie
        self.headers = {
            "User-Agent": UA,
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

            return KuaiShouVideo.parse(cast(dict[str, Any], data))

    @staticmethod
    def get_video_id(url: str) -> str:
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
    def parse(cls, data: dict) -> Self:
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


@dataclass
class KuaishouImage:
    url: str
    w: int = 0
    h: int = 0
    e: str = "webp"


@dataclass
class KuaishouVideo:
    url: str
    w: int = 0
    h: int = 0
    d: int = 0


class KuaishouParser:
    def __init__(self, real_url, proxy: str | None = None, cookie: dict | None = None):
        self.real_url = real_url
        self.proxy = proxy
        self.cookie = cookie
        self.html_content = None
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
            ),
            "referer": "https://www.kuaishou.com/",
        }
        self.video_id = self._get_video_id(self.real_url)
        self.page_type = "UNKNOWN"
        self.structured_data: dict = {}
        self.client: dict = {}

    @classmethod
    async def create(cls, real_url, proxy: str | None = None, cookie: dict | None = None):
        parser = cls(real_url, proxy, cookie)
        # 快手不同公开路由的稳定性差异较大，命中风控时自动切换备用路由重试。
        await parser._load_page_with_fallbacks()
        # 提取核心数据客户端对象
        parser.client = (
            parser.structured_data.get("defaultClient", {}) if parser.page_type == "VIDEO" else parser.structured_data
        )
        return parser

    @staticmethod
    def _get_video_id(url):
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            for parameter in ("vid", "id", "modal_id", "v", "s", "pid"):
                video_id = query_params.get(parameter, [None])[0]
                if video_id:
                    return video_id
            path_segments = parsed_url.path.strip("/").split("/")
            if path_segments:
                video_id = path_segments[-1]
                return video_id.removesuffix(".html")
            logger.warning(f"Unable to retrieve video ID from URL: {url}")
        except Exception as e:
            logger.error(f"An error occurred while extracting video ID: {e}")
        return None

    @staticmethod
    def _is_blocked_payload(html_content):
        if not html_content:
            return False
        try:
            payload = json.loads(html_content)
        except (TypeError, json.JSONDecodeError):
            return False
        return payload.get("result") == 2

    def _candidate_urls(self):
        if not self.video_id:
            return [self.real_url]
        candidates = [self.real_url]
        if not self._is_fw_photo_url(self.real_url):
            candidates.append(f"https://v.m.chenzhongtech.com/fw/photo/{self.video_id}")
        deduped = []
        for url in candidates:
            if url and url not in deduped:
                deduped.append(url)
        return deduped

    @staticmethod
    def _is_fw_photo_url(url):
        if not url:
            return False
        path = urlparse(url).path.rstrip("/")
        return path.startswith("/fw/photo/")

    def _build_lightweight_headers(self):
        return {
            "User-Agent": "Mozilla/5.0",
            "referer": "https://www.kuaishou.com/",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def _fetch_html_with_headers(self, url, headers):
        try:
            async with httpx.AsyncClient(timeout=15, cookies=self.cookie, proxy=self.proxy) as client:
                resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
        except httpx.RequestError as e:
            logger.error(f"Failed to get the page: {url}, Error: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get the page: {url}, Error: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching {url}: {e}")
            return None

    def _is_valid_video_state(self, page_type, structured_data):
        if not structured_data:
            return False
        if page_type == "ATLAS":
            payload = self._find_nested_dict(structured_data, ("photo",))
            if not payload:
                return False
            photo = payload.get("photo", {})
            if not isinstance(photo, dict):
                return False
            return bool(
                photo.get("caption")
                or photo.get("coverUrls")
                or photo.get("webpCoverUrls")
                or photo.get("mainMvUrls")
                or photo.get("manifest")
                or payload.get("atlas")
            )
        if page_type != "VIDEO":
            return True
        default_client = structured_data.get("defaultClient", {})
        if not isinstance(default_client, dict):
            return False
        if default_client.get("VisionVideoSetRepresentation:1"):
            return True
        for key in default_client.keys():
            if "visionVideoDetail" in key or "VisionVideoDetailPhoto:" in key:
                return True
        return False

    async def _try_parse_candidate(self, candidate_url, headers):
        self.real_url = candidate_url
        self.html_content = await self._fetch_html_with_headers(candidate_url, headers)
        if self._is_blocked_payload(self.html_content):
            logger.warning(f"Kuaishou blocked route {candidate_url}, trying fallback")
            return False
        page_type, structured_data = self._identify_and_parse_data()
        if page_type == "UNKNOWN" or not structured_data:
            return False
        if not self._is_valid_video_state(page_type, structured_data):
            logger.warning(f"Kuaishou route {candidate_url} returned incomplete video state, trying fallback")
            return False
        self.page_type = page_type
        self.structured_data = structured_data
        return True

    async def _load_page_with_fallbacks(self):
        for candidate_url in self._candidate_urls():
            if await self._try_parse_candidate(candidate_url, self.headers):
                return
            if await self._try_parse_candidate(candidate_url, self._build_lightweight_headers()):
                return
        self.page_type = "UNKNOWN"
        self.structured_data = {}

    def _extract_json_object(self, text, start_index):
        """稳健提取 JSON 对象：通过括号匹配解决额外数据报错"""
        if start_index == -1 or not text:
            return None
        bracket_count = 0
        in_string = False
        escape_next = False
        quote_char = ""
        for i in range(start_index, len(text)):
            char = text[i]
            if in_string:
                if escape_next:
                    escape_next = False
                elif char == "\\":
                    escape_next = True
                elif char == quote_char:
                    in_string = False
                continue
            if char in ("'", '"'):
                in_string = True
                quote_char = char
            elif char == "{":
                bracket_count += 1
            elif char == "}":
                bracket_count -= 1
                if bracket_count == 0:
                    return text[start_index : i + 1]
        return None

    def _find_nested_dict(self, data, required_keys):
        """在快手扁平状态里查找同时具备指定字段的节点。"""
        stack = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if all(key in current for key in required_keys):
                    return current
                stack.extend(value for value in current.values() if isinstance(value, (dict, list)))
            elif isinstance(current, list):
                stack.extend(item for item in current if isinstance(item, (dict, list)))
        return {}

    def _get_atlas_payload(self):
        if self.page_type not in ("ATLAS", "VIDEO"):
            return {}
        payload = self._find_nested_dict(self.structured_data, ("atlas", "photo"))
        if payload:
            return payload
        payload = self._find_nested_dict(self.structured_data, ("photo",))
        if payload:
            return payload
        return {}

    def _get_atlas_variants(self):
        payload = self._get_atlas_payload()
        photo = payload.get("photo", {})
        variants = []
        ext_atlas = photo.get("ext_params", {}).get("atlas")
        if isinstance(ext_atlas, dict):
            variants.append(ext_atlas)
        atlas = payload.get("atlas")
        if isinstance(atlas, dict):
            variants.append(atlas)
        return variants

    @staticmethod
    def _atlas_is_webp(atlas):
        image_paths = atlas.get("list") or []
        return any(str(path).lower().endswith(".webp") for path in image_paths)

    @staticmethod
    def _normalize_url(url):
        if not url:
            return None
        url = str(url).replace("\\u002F", "/")
        if url.startswith("//"):
            return f"https:{url}"
        return url

    def _first_url(self, candidates):
        if isinstance(candidates, str):
            return self._normalize_url(candidates)
        if not isinstance(candidates, list):
            return None
        for item in candidates:
            if isinstance(item, str):
                return self._normalize_url(item)
            if isinstance(item, dict) and item.get("url"):
                return self._normalize_url(item.get("url"))
        return None

    @staticmethod
    def _first_cdn(atlas):
        cdn_list = atlas.get("cdn") or []
        if not cdn_list:
            cdn_list = [
                item.get("cdn") for item in atlas.get("cdnList", []) if isinstance(item, dict) and item.get("cdn")
            ]
        if isinstance(cdn_list, str):
            return cdn_list
        return cdn_list[0] if cdn_list else None

    def _build_resource_url(self, cdn, path):
        path = self._normalize_url(path)
        if not path:
            return None
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("//"):
            return f"https:{path}"
        if not cdn:
            return path
        cdn = self._normalize_url(cdn).rstrip("/")
        if not cdn.startswith("http://") and not cdn.startswith("https://"):
            cdn = f"https://{cdn}"
        return f"{cdn}/{path.lstrip('/')}"

    def _identify_and_parse_data(self):
        """识别快手不同的数据载体（Apollo 或 InitState）"""
        if not self.html_content:
            return "UNKNOWN", {}
        # 1. 视频详情页 (Apollo)
        if "window.__APOLLO_STATE__" in self.html_content:
            marker = "window.__APOLLO_STATE__"
            start_pos = self.html_content.find(marker) + len(marker)
            start_pos = self.html_content.find("{", start_pos)
            json_str = self._extract_json_object(self.html_content, start_pos)
            if json_str:
                try:
                    return "VIDEO", json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode Kuaishou Apollo data: {e}")
        # 2. 某些图文或移动端适配页 (INIT_STATE)
        if "window.INIT_STATE" in self.html_content:
            marker = "window.INIT_STATE"
            start_pos = self.html_content.find(marker) + len(marker)
            start_pos = self.html_content.find("{", start_pos)
            json_str = self._extract_json_object(self.html_content, start_pos)
            if json_str:
                try:
                    return "ATLAS", json.loads(json_str, strict=False)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode Kuaishou INIT_STATE data: {e}")
        return "UNKNOWN", {}

    def get_real_video_url(self):
        try:
            if self.page_type == "VIDEO":
                # 优先从标准表示层获取
                vvsr = self.client.get("VisionVideoSetRepresentation:1", {})
                video_url = vvsr.get("url")
                w, h = vvsr.get("width", 0), vvsr.get("height", 0)
                d = self.client.get("VisionVideoAdaptationSet:1", {}).get("duration", 0)
                # 兜底：直接从 Photo 对象获取
                if not video_url:
                    photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
                    vvdp = self.client.get(photo_key, {})
                    video_url = vvdp.get("photoUrl")
                    d = vvdp.get("duration", 0)
                if not video_url:
                    return None
                return KuaishouVideo(url=video_url.replace("\u002f", "/"), w=w, h=h, d=d)
            payload = self._get_atlas_payload()
            photo = payload.get("photo", {})
            video_url = self._first_url(photo.get("mainMvUrls")) or self._first_url(photo.get("photoUrls"))
            if video_url:
                return KuaishouVideo(video_url)
            manifest = photo.get("manifest", {})
            for adaptation_set in manifest.get("adaptationSet", []):
                d = adaptation_set.get("duration", 0)
                for representation in adaptation_set.get("representation", []):
                    backup_urls = representation.get("backupUrl") or []
                    if backup_urls:
                        w, h = representation.get("width", 0), representation.get("height", 0)
                        return KuaishouVideo(self._first_url(backup_urls), w=w, h=h, d=d)
                    m3u8_slice = representation.get("m3u8Slice")
                    if m3u8_slice and "http" in m3u8_slice:
                        for line in m3u8_slice.splitlines():
                            line = line.strip()
                            if line.startswith("http://") or line.startswith("https://"):
                                return KuaishouVideo(line)
        except Exception as e:
            logger.warning(f"Failed to parse video URL: {e}")
            return None
        return None

    def get_title_content(self):
        try:
            photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
            if self.page_type == "VIDEO":
                title = self.client.get(photo_key, {}).get("caption", "")
                if title:
                    return title
            if self.page_type in ("ATLAS", "VIDEO"):
                payload = self._get_atlas_payload()
                return payload.get("photo", {}).get("caption", "")
        except Exception as e:
            logger.warning(f"Failed to parse title content: {e}")
            pass
        return ""

    def get_cover_photo_url(self):
        try:
            photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
            if self.page_type == "VIDEO":
                cover_url = self.client.get(photo_key, {}).get("coverUrl", "")
                if cover_url:
                    return cover_url
            if self.page_type in ("ATLAS", "VIDEO"):
                payload = self._get_atlas_payload()
                photo = payload.get("photo", {})
                cover_url = (
                    self._first_url(photo.get("coverUrls"))
                    or self._first_url(photo.get("webpCoverUrls"))
                    or self._first_url(self.get_image_list())
                )
                return cover_url or ""
        except Exception as e:
            logger.warning(f"Failed to parse cover URL: {e}")
            pass
        return ""

    def get_image_list(self) -> list[KuaishouImage]:
        try:
            if self.page_type not in ("ATLAS", "VIDEO"):
                return []
            atlas_variants = self._get_atlas_variants()
            preferred_atlas = next(
                (atlas for atlas in atlas_variants if self._atlas_is_webp(atlas)),
                atlas_variants[0] if atlas_variants else {},
            )
            path_list = preferred_atlas.get("list", [])
            if not path_list:
                return []
            size = preferred_atlas.get("size", [])
            get_size = len(path_list) == len(size)
            image_urls = []
            w = h = 0
            for i, image_path in enumerate(path_list):
                if get_size:
                    w, h = int(size[i]["w"]), int(size[i]["h"])

                if image_url := self._build_resource_url(self._first_cdn(preferred_atlas), image_path):
                    image_urls.append(KuaishouImage(image_url, w=w, h=h))
            return image_urls

        except Exception as e:
            logger.warning(f"Failed to parse image list: {e}")
            return []
