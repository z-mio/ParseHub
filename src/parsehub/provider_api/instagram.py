from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

import httpx


class InstagramAPIError(RuntimeError):
    """Instagram 接口请求或响应解析失败。"""


class InstagramMediaType(StrEnum):
    IMAGE = "GraphImage"
    VIDEO = "GraphVideo"
    SIDECAR = "GraphSidecar"


@dataclass(slots=True)
class InstagramSidecarNode:
    is_video: bool
    display_url: str
    video_url: str | None
    width: int
    height: int


class InstagramPost:
    """轻量版 Instagram Post，只保留当前项目解析帖子需要的字段。"""

    _XDT_TYPES = {
        "XDTGraphImage": InstagramMediaType.IMAGE,
        "XDTGraphVideo": InstagramMediaType.VIDEO,
        "XDTGraphSidecar": InstagramMediaType.SIDECAR,
    }

    def __init__(self, node: dict[str, Any]):
        self._node = node
        self._normalize_typename()

    def _normalize_typename(self) -> None:
        typename = self._node.get("__typename")
        if typename in self._XDT_TYPES:
            self._node["__typename"] = self._XDT_TYPES[typename]

    def _field(self, *keys: str) -> Any:
        value: Any = self._node
        for key in keys:
            value = value[key]
        return value

    @property
    def shortcode(self) -> str:
        return str(self._node.get("shortcode") or self._node["code"])

    @property
    def typename(self) -> InstagramMediaType:
        return InstagramMediaType(self._field("__typename"))

    @property
    def is_video(self) -> bool:
        return bool(self._field("is_video"))

    @property
    def title(self) -> str | None:
        return self._node.get("title")

    @property
    def caption(self) -> str | None:
        caption_edges = self._node.get("edge_media_to_caption", {}).get("edges") or []
        if caption_edges:
            if text := caption_edges[0].get("node", {}).get("text"):
                return str(text)
            return None
        return self._node.get("caption")

    @property
    def url(self) -> str:
        return str(self._node.get("display_url") or self._node["display_src"])

    @property
    def video_url(self) -> str | None:
        if not self.is_video:
            return None
        return self._node.get("video_url")

    @property
    def video_duration(self) -> float | None:
        value = self._node.get("video_duration")
        return float(value) if value is not None else None

    @property
    def width(self) -> int:
        return int(self._node.get("dimensions", {}).get("width") or 0)

    @property
    def height(self) -> int:
        return int(self._node.get("dimensions", {}).get("height") or 0)

    def get_sidecar_nodes(self, start: int = 0, end: int = -1) -> Iterator[InstagramSidecarNode]:
        if self.typename is not InstagramMediaType.SIDECAR:
            return

        edges = self._field("edge_sidecar_to_children", "edges")
        if end < 0:
            end = len(edges) - 1
        if start < 0:
            start = len(edges) - 1

        for idx, edge in enumerate(edges):
            if not start <= idx <= end:
                continue

            node = edge["node"]
            dimensions = node.get("dimensions", {})
            is_video = bool(node.get("is_video"))
            yield InstagramSidecarNode(
                is_video=is_video,
                display_url=node.get("display_url") or node.get("display_src") or "",
                video_url=node.get("video_url") if is_video else None,
                width=int(dimensions.get("width") or 0),
                height=int(dimensions.get("height") or 0),
            )


class InstagramAPI:
    GRAPHQL_URL = "https://www.instagram.com/graphql/query"
    INSTAGRAM_URL = "https://www.instagram.com/"
    SHORTCODE_DOC_ID = "27128499623469141"

    DEFAULT_COOKIES = {
        "sessionid": "",
        "mid": "",
        "ig_pr": "1",
        "ig_vw": "1920",
        "csrftoken": "",
        "s_network": "",
        "ds_user_id": "",
    }

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    MEDIA_TYPES = {
        1: InstagramMediaType.IMAGE,
        2: InstagramMediaType.VIDEO,
        8: InstagramMediaType.SIDECAR,
    }

    def __init__(
        self,
        *,
        proxy: str | None = None,
        cookie: dict[str, str] | None = None,
        timeout: float = 30,
        user_agent: str | None = None,
    ):
        self.proxy = proxy
        self.cookie = cookie or {}
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    async def get_post(self, shortcode: str) -> InstagramPost:
        media = await self.get_shortcode_media(shortcode)
        return InstagramPost(media)

    async def get_shortcode_media(self, shortcode: str) -> dict[str, Any]:
        payload = await self._post_graphql(
            doc_id=self.SHORTCODE_DOC_ID,
            variables={
                "shortcode": shortcode,
                "__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider": False,
            },
        )

        media = self._extract_shortcode_media(payload)
        if media is None:
            raise InstagramAPIError("Fetching Post metadata failed.")
        return media

    async def _post_graphql(self, *, doc_id: str, variables: dict[str, Any]) -> dict[str, Any]:
        async with self._new_client() as client:
            await self._ensure_csrf_token(client)
            data = {
                "variables": json.dumps(variables, separators=(",", ":")),
                "doc_id": doc_id,
                "server_timestamps": "true",
            }

            try:
                response = await client.post(self.GRAPHQL_URL, data=data, follow_redirects=False)
            except httpx.HTTPError as exc:
                raise InstagramAPIError(f"请求 Instagram GraphQL 失败: {exc}") from exc

        if response.status_code != 200:
            raise InstagramAPIError(f"Instagram GraphQL 返回 HTTP {response.status_code}: {response.text[:500]}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise InstagramAPIError(f"Instagram GraphQL 返回非 JSON 响应: {response.text[:500]}") from exc

        if payload.get("status") not in (None, "ok"):
            raise InstagramAPIError(f"Instagram GraphQL 状态异常: {payload!r}")
        return cast(dict[str, Any], payload)

    def _extract_shortcode_media(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise InstagramAPIError(f"响应缺少 data: {payload!r}")

        old_media = data.get("xdt_shortcode_media")
        if isinstance(old_media, dict):
            return old_media
        if old_media is None and "xdt_shortcode_media" in data:
            return None

        web_info = data.get("xdt_api__v1__media__shortcode__web_info")
        if not isinstance(web_info, dict):
            raise InstagramAPIError(f"响应缺少 shortcode web_info: {payload!r}")

        items = web_info.get("items") or []
        if not items:
            return None
        if not isinstance(items[0], dict):
            raise InstagramAPIError(f"shortcode web_info.items[0] 类型异常: {type(items[0]).__name__}")
        return self._convert_v1_media(items[0])

    def _convert_v1_media(self, media: dict[str, Any]) -> dict[str, Any]:
        media_type = self._media_type(media)
        typename = self.MEDIA_TYPES.get(media_type, InstagramMediaType.IMAGE)
        caption = media.get("caption")
        caption_text = caption.get("text") if isinstance(caption, dict) else caption
        image_candidate = self._first_image_candidate(media)
        video_version = self._first_video_version(media)

        node: dict[str, Any] = {
            "shortcode": media.get("code", ""),
            "id": media.get("pk", ""),
            "__typename": typename,
            "is_video": media_type == 2,
            "taken_at_timestamp": media.get("taken_at"),
            "edge_media_to_caption": {
                "edges": [{"node": {"text": caption_text}}] if caption_text else [],
            },
            "edge_media_preview_like": {"count": media.get("like_count") or 0},
            "edge_media_to_parent_comment": {
                "count": media.get("comment_count") or 0,
                "edges": [],
            },
            "owner": self._convert_owner(media.get("user")),
            "dimensions": self._dimensions_from_candidate(image_candidate),
            "display_url": image_candidate.get("url", ""),
        }

        for source_key, target_key in (
            ("title", "title"),
            ("has_liked", "viewer_has_liked"),
            ("accessibility_caption", "accessibility_caption"),
            ("location", "location"),
            ("video_duration", "video_duration"),
            ("view_count", "video_view_count"),
            ("play_count", "video_play_count"),
        ):
            if media.get(source_key) is not None:
                node[target_key] = media[source_key]

        if video_version.get("url"):
            node["video_url"] = video_version["url"]

        carousel_media = media.get("carousel_media") or []
        if carousel_media:
            node["edge_sidecar_to_children"] = {
                "edges": [{"node": self._convert_v1_sidecar_item(item)} for item in carousel_media],
            }

        return node

    def _convert_v1_sidecar_item(self, item: dict[str, Any]) -> dict[str, Any]:
        media_type = self._media_type(item)
        typename = self.MEDIA_TYPES.get(media_type, InstagramMediaType.IMAGE)
        image_candidate = self._first_image_candidate(item)
        video_version = self._first_video_version(item)
        is_video = media_type == 2

        node: dict[str, Any] = {
            "shortcode": item.get("code", ""),
            "__typename": typename,
            "is_video": is_video,
            "display_url": image_candidate.get("url", ""),
            "video_url": video_version.get("url") if is_video else None,
            "dimensions": self._dimensions_from_candidate(image_candidate),
        }
        if item.get("accessibility_caption") is not None:
            node["accessibility_caption"] = item["accessibility_caption"]
        return node

    @staticmethod
    def _media_type(media: dict[str, Any]) -> int:
        value = media.get("media_type")
        return value if isinstance(value, int) else 0

    @staticmethod
    def _convert_owner(user: Any) -> dict[str, Any]:
        if not isinstance(user, dict):
            return {"id": "", "username": "", "full_name": ""}
        return {
            "id": user.get("pk", ""),
            "username": user.get("username", ""),
            "full_name": user.get("full_name", ""),
        }

    @staticmethod
    def _first_image_candidate(media: dict[str, Any]) -> dict[str, Any]:
        candidates = media.get("image_versions2", {}).get("candidates") or []
        return candidates[0] if candidates and isinstance(candidates[0], dict) else {}

    @staticmethod
    def _first_video_version(media: dict[str, Any]) -> dict[str, Any]:
        versions = media.get("video_versions") or []
        return versions[0] if versions and isinstance(versions[0], dict) else {}

    @staticmethod
    def _dimensions_from_candidate(candidate: dict[str, Any]) -> dict[str, int]:
        return {
            "width": int(candidate.get("width") or 0),
            "height": int(candidate.get("height") or 0),
        }

    async def _ensure_csrf_token(self, client: httpx.AsyncClient) -> None:
        csrf_token = self._get_cookie_value(client, "csrftoken")
        if not csrf_token:
            try:
                await client.get(self.INSTAGRAM_URL, follow_redirects=True)
            except httpx.HTTPError as exc:
                raise InstagramAPIError(f"获取 Instagram csrftoken 失败: {exc}") from exc
            csrf_token = self._get_cookie_value(client, "csrftoken")

        if not csrf_token:
            raise InstagramAPIError("无法获取 Instagram csrftoken")
        client.headers["x-csrftoken"] = csrf_token

    @staticmethod
    def _get_cookie_value(client: httpx.AsyncClient, name: str) -> str:
        values = [cookie.value for cookie in client.cookies.jar if cookie.name == name and cookie.value]
        return values[-1] if values else ""

    def _new_client(self) -> httpx.AsyncClient:
        cookies = self.DEFAULT_COOKIES | self.cookie
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.instagram.com/",
            "User-Agent": self.user_agent,
            "authority": "www.instagram.com",
            "scheme": "https",
        }
        return httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            proxy=self.proxy,
            timeout=self.timeout,
        )


__all__ = [
    "InstagramAPI",
    "InstagramAPIError",
    "InstagramMediaType",
    "InstagramPost",
    "InstagramSidecarNode",
]
