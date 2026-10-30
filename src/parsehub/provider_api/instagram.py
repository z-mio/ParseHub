from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from curl_cffi import requests

from ..types import ContentUnavailableError


class InstagramAPIError(RuntimeError):
    """Instagram 接口请求或响应解析失败。"""


class InstagramRestrictedError(InstagramAPIError):
    """Instagram 内容受限。"""


class InstagramMediaType(StrEnum):
    IMAGE = "GraphImage"
    VIDEO = "GraphVideo"
    SIDECAR = "GraphSidecar"


@dataclass(slots=True, kw_only=True)
class InstagramMedia:
    is_video: bool
    display_url: str
    video_url: str = ""
    width: int = 0
    height: int = 0
    duration: float = 0


@dataclass(slots=True, kw_only=True)
class InstagramPost:
    shortcode: str
    type: InstagramMediaType
    caption: str = ""
    title: str = ""
    media: list[InstagramMedia]

    @classmethod
    def from_v1(cls, item: dict[str, Any]) -> InstagramPost:
        media_type = _v1_type(item)
        if media_type is InstagramMediaType.SIDECAR:
            media_items = item.get("carousel_media") or []
            if not media_items:
                raise InstagramAPIError("未返回帖子数据")
        else:
            media_items = [item]
        if not all(isinstance(media_item, dict) for media_item in media_items):
            raise InstagramAPIError("Instagram 帖子数据格式无效")
        return cls(
            shortcode=str(item.get("code") or item.get("shortcode") or ""),
            type=media_type,
            caption=_caption_text(item.get("caption")),
            title=str(item.get("title") or ""),
            media=[_v1_media(media_item) for media_item in media_items],
        )

    @classmethod
    def from_graph(cls, node: dict[str, Any]) -> InstagramPost:
        media_type = _graph_type(node)
        if media_type is InstagramMediaType.SIDECAR:
            edges = (node.get("edge_sidecar_to_children") or {}).get("edges") or []
            if not edges:
                raise InstagramAPIError("未返回帖子数据")
            media = [_graph_media(edge.get("node") or {}) for edge in edges]
        else:
            media = [_graph_media(node)]

        caption_edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
        caption = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""
        return cls(
            shortcode=str(node.get("shortcode") or node.get("code") or ""),
            type=media_type,
            caption=str(caption or node.get("caption") or ""),
            title=str(node.get("title") or ""),
            media=media,
        )


class InstagramAPI:
    HOME_URL = "https://www.instagram.com/"
    GRAPHQL_URL = "https://www.instagram.com/api/graphql"
    EMBED_URL = "https://www.instagram.com/{kind}/{shortcode}/embed/captioned/"
    MEDIA_INFO_URL = "https://www.instagram.com/api/v1/media/{media_id}/info/"
    RULING_URL = "https://www.instagram.com/api/v1/web/get_ruling_for_content/"
    APP_ID = "936619743392459"
    ASBD_ID = "359341"
    DOC_ID = "27130156389949648"
    MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"

    def __init__(
        self,
        *,
        proxy: str | None = None,
        cookie: dict[str, str] | None = None,
        timeout: float = 30,
    ):
        self.proxy = proxy
        self.cookie = cookie or {}
        self.timeout = timeout

    async def get_post(self, shortcode: str) -> InstagramPost:
        try:
            async with requests.AsyncSession(
                impersonate="chrome",
                proxy=self.proxy,
                timeout=self.timeout,
                cookies=self.cookie or None,
            ) as session:
                if self.cookie:
                    return await self._get_cookie_post(session, shortcode)
                return await self._get_logged_out_post(session, shortcode)
        except requests.RequestsError as exc:
            raise InstagramAPIError(f"请求 Instagram 失败: {exc}") from exc

    async def _get_logged_out_post(self, session: requests.AsyncSession, shortcode: str) -> InstagramPost:
        detail = "未返回帖子数据"
        media_id = str(self.shortcode_to_media_id(shortcode))

        try:
            item = await self._fetch_graphql(session, shortcode, media_id)
            if item is not None:
                return InstagramPost.from_v1(item)
        except InstagramAPIError as exc:
            detail = str(exc)
        except requests.RequestsError as exc:
            detail = f"请求 Instagram 失败: {exc}"

        try:
            node = await self._fetch_embed(session, shortcode)
            if node is not None:
                return InstagramPost.from_graph(node)
        except InstagramAPIError as exc:
            detail = str(exc)
        except requests.RequestsError as exc:
            detail = f"请求 Instagram Embed 失败: {exc}"

        await self._check_ruling(session, media_id)
        raise InstagramAPIError(detail)

    async def _fetch_graphql(
        self, session: requests.AsyncSession, shortcode: str, media_id: str
    ) -> dict[str, Any] | None:
        response = await session.get(self.HOME_URL)
        if response.status_code != 200:
            raise InstagramAPIError(f"HTTP {response.status_code}: {response.text[:300]}")

        match = re.search(r'\["LSD",\[\],\{"token":"([^"]+)"', response.text)
        if not match:
            raise InstagramAPIError(f"未能获取 Instagram LSD token: {response.text[:300]}")
        lsd = match.group(1)
        csrf = session.cookies.get("csrftoken", "")
        headers = {
            "X-IG-App-ID": self.APP_ID,
            "X-ASBD-ID": self.ASBD_ID,
            "X-IG-WWW-Claim": "0",
            "Origin": self.HOME_URL.rstrip("/"),
            "Accept": "*/*",
            "X-FB-Friendly-Name": "PolarisLoggedOutDesktopWWWPostRootContentQuery",
            "X-CSRFToken": csrf,
            "X-FB-LSD": lsd,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/p/{shortcode}/",
        }
        data = {
            "lsd": lsd,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "PolarisLoggedOutDesktopWWWPostRootContentQuery",
            "server_timestamps": "true",
            "variables": json.dumps({"media_id": media_id}, separators=(",", ":")),
            "doc_id": self.DOC_ID,
        }
        response = await session.post(self.GRAPHQL_URL, headers=headers, data=data)
        if response.status_code != 200:
            raise InstagramAPIError(f"HTTP {response.status_code}: {response.text[:300]}")
        payload = _response_json(response)
        graphql_data = payload.get("data")
        media = graphql_data.get("xig_polaris_media") if isinstance(graphql_data, dict) else None
        item = media.get("if_not_gated_logged_out") if isinstance(media, dict) else None
        if isinstance(item, dict):
            return item
        errors = payload.get("errors")
        if errors:
            raise InstagramAPIError(str(errors[0])[:300])
        return None

    async def _fetch_embed(self, session: requests.AsyncSession, shortcode: str) -> dict[str, Any] | None:
        for kind in ("p", "reel"):
            response = await session.get(
                self.EMBED_URL.format(kind=kind, shortcode=shortcode),
                headers={"Accept": "text/html", "User-Agent": self.MOBILE_USER_AGENT},
                allow_redirects=False,
            )
            if response.status_code != 200:
                continue
            node = self._extract_embed_media(response.text)
            if node is not None:
                return node
        return None

    @staticmethod
    def _extract_embed_media(html: str) -> dict[str, Any] | None:
        match = re.search(r'"init",\[\],\[(.*?)\]\],', html, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(f"[{match.group(1)}]")
            context = payload[0].get("contextJSON")
            context = json.loads(context) if isinstance(context, str) else context
        except (IndexError, AttributeError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(context, dict):
            return None
        node = (context.get("gql_data") or {}).get("shortcode_media")
        return node if isinstance(node, dict) else None

    async def _check_ruling(self, session: requests.AsyncSession, media_id: str) -> None:
        try:
            response = await session.get(
                self.RULING_URL,
                params={"content_type": "MEDIA", "target_id": media_id},
                headers={"X-IG-App-ID": self.APP_ID, "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            body = _response_json(response)
        except (InstagramAPIError, requests.RequestsError):
            return

        if body.get("message") == "Media cannot be found":
            raise ContentUnavailableError("帖子不存在或已被删除")
        if title := body.get("title"):
            description = body.get("description")
            raise InstagramRestrictedError(f"{title}: {description}" if description else str(title))

    async def _get_cookie_post(self, session: requests.AsyncSession, shortcode: str) -> InstagramPost:
        media_id = self.shortcode_to_media_id(shortcode)
        response = await session.get(
            self.MEDIA_INFO_URL.format(media_id=media_id),
            headers={
                "X-IG-App-ID": self.APP_ID,
                "X-ASBD-ID": self.ASBD_ID,
                "X-IG-WWW-Claim": "0",
                "X-CSRFToken": self.cookie.get("csrftoken", ""),
                "Origin": self.HOME_URL.rstrip("/"),
                "Referer": f"https://www.instagram.com/p/{shortcode}/",
            },
            allow_redirects=False,
        )
        location = response.headers.get("Location", "")
        redirect_path = urlparse(location).path
        if response.status_code in (301, 302, 303, 307, 308) and (
            redirect_path.startswith("/accounts/login") or redirect_path == "/"
        ):
            raise InstagramAPIError("Cookie 已失效")
        if response.status_code != 200:
            raise InstagramAPIError(f"HTTP {response.status_code}: {response.text[:300]}")

        payload = _response_json(response)
        items = payload.get("items") or []
        if not items or not isinstance(items[0], dict):
            raise InstagramAPIError("未返回帖子数据")
        return InstagramPost.from_v1(items[0])

    @staticmethod
    def shortcode_to_media_id(shortcode: str) -> int:
        if len(shortcode) > 28:
            shortcode = shortcode[:-28]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        media_id = 0
        for char in shortcode:
            media_id = media_id * 64 + alphabet.index(char)
        return media_id


def _response_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except (ValueError, requests.RequestsError) as exc:
        raise InstagramAPIError(f"Instagram 返回无效 JSON: {response.text[:300]}") from exc
    if not isinstance(payload, dict):
        raise InstagramAPIError("Instagram 返回的数据格式无效")
    return payload


def _caption_text(caption: Any) -> str:
    if isinstance(caption, dict):
        caption = caption.get("text")
    return str(caption or "")


def _v1_type(item: dict[str, Any]) -> InstagramMediaType:
    media_types = {
        1: InstagramMediaType.IMAGE,
        2: InstagramMediaType.VIDEO,
        8: InstagramMediaType.SIDECAR,
    }
    media_type = item.get("media_type")
    if isinstance(media_type, int) and media_type in media_types:
        return media_types[media_type]
    raise InstagramAPIError(f"不支持的 Instagram 媒体类型: {media_type}")


def _v1_media(item: dict[str, Any]) -> InstagramMedia:
    candidates = (item.get("image_versions2") or {}).get("candidates") or []
    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    video_versions = item.get("video_versions") or []
    video = video_versions[0] if video_versions and isinstance(video_versions[0], dict) else {}
    video_url = str(video.get("url") or "")
    return InstagramMedia(
        is_video=bool(video_url),
        display_url=str(candidate.get("url") or item.get("display_url") or ""),
        video_url=video_url,
        width=int(item.get("original_width") or candidate.get("width") or 0),
        height=int(item.get("original_height") or candidate.get("height") or 0),
        duration=float(item.get("video_duration") or 0),
    )


def _graph_type(node: dict[str, Any]) -> InstagramMediaType:
    typename = node.get("__typename")
    if not isinstance(typename, str):
        raise InstagramAPIError(f"不支持的 Instagram 媒体类型: {typename}")
    try:
        return InstagramMediaType(typename)
    except ValueError as exc:
        raise InstagramAPIError(f"不支持的 Instagram 媒体类型: {typename}") from exc


def _graph_media(node: dict[str, Any]) -> InstagramMedia:
    video_url = str(node.get("video_url") or "")
    dimensions = node.get("dimensions") or {}
    return InstagramMedia(
        is_video=bool(video_url),
        display_url=str(node.get("display_url") or node.get("display_src") or ""),
        video_url=video_url,
        width=int(dimensions.get("width") or 0),
        height=int(dimensions.get("height") or 0),
        duration=float(node.get("video_duration") or 0),
    )


__all__ = [
    "InstagramAPI",
    "InstagramAPIError",
    "InstagramMedia",
    "InstagramMediaType",
    "InstagramPost",
    "InstagramRestrictedError",
]
