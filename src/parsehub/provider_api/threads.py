from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from ..utils.helpers import UA


class ThreadsAPIError(Exception):
    """Threads API 相关错误"""


class ThreadsAPI:
    GRAPHQL_URL = "https://www.threads.com/graphql/query"
    THREADS_URL = "https://www.threads.com/"
    # BarcelonaPostPageDirectQuery, 通过帖子 ID 获取帖子内容
    POST_DOC_ID = "27419285281047858"
    X_IG_APP_ID = "238260118697367"
    # shortcode <-> pk 使用与 Instagram 相同的 base64 字母表
    SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

    # Threads 与 Instagram 共用 Meta 的登录后端, 因此使用同一套 Cookie 键
    DEFAULT_COOKIES = {
        "sessionid": "",
        "ds_user_id": "",
        "csrftoken": "",
        "mid": "",
        "ig_did": "",
    }

    # GraphQL 查询强制要求的 relay provider 变量: 必须全部传入 (值统一给 False 即可),
    # 缺失或只传部分都会导致查询返回 execution error.
    # 与 Instagram 的 doc_id 一样, 该列表会随 Threads 前端更新而变化, 需要时同步维护.
    RELAY_PROVIDERS = (
        "BarcelonaHasPermalinkIndentation",
        "BarcelonaIsLoggedIn",
        "BarcelonaHasPostAuthorNotifControls",
        "BarcelonaShouldShowFediverseM1Features",
        "BarcelonaHasPermalinkPodcastCard",
        "BarcelonaHasDearAlgoConsumption",
        "BarcelonaHasEventBadge",
        "BarcelonaGenAIRepliesEnabled",
        "BarcelonaIsSearchDiscoveryEnabled",
        "BarcelonaHasCommunities",
        "BarcelonaHasGameScoreShare",
        "BarcelonaHasPublicViewCountCard",
        "BarcelonaHasCommunityEntityCard",
        "BarcelonaHasScorecardCommunity",
        "BarcelonaHasSportTeamAllegianceCard",
        "BarcelonaHasMusic",
        "BarcelonaHasNewspaperLinkStyle",
        "BarcelonaHasMessaging",
        "BarcelonaHasPodcastTextFragments",
        "BarcelonaShouldFulfillLightboxQuery",
        "BarcelonaHasViewerReplied",
        "BarcelonaHasPrivateRepliesDeprecation",
        "BarcelonaHasGhostPostEmojiActivation",
        "BarcelonaOptionalCookiesEnabled",
        "BarcelonaHasDearAlgoWebProduction",
        "BarcelonaHasWebFavicons",
        "BarcelonaIsCrawler",
        "BarcelonaHasCommunityTopContributors",
        "BarcelonaCanSeeSponsoredContent",
        "BarcelonaShouldShowFediverseM075Features",
        "BarcelonaIsInternalUser",
    )

    def __init__(
        self,
        proxy: str | None = None,
        cookie: dict[str, str] | None = None,
        timeout: float = 30,
    ):
        self.proxy = proxy
        self.cookie = cookie or {}
        self.timeout = timeout

    async def parse(self, url: str) -> ThreadsPost:
        code = self.get_post_id_by_url(url)
        payload = await self._post_graphql(
            doc_id=self.POST_DOC_ID,
            variables=self._build_variables(code),
        )
        post = self._extract_post(payload, code)
        if post is None:
            raise ThreadsAPIError("Fetching Post metadata failed.")
        return ThreadsPost.from_graphql(post)

    def _build_variables(self, code: str) -> dict[str, Any]:
        variables: dict[str, Any] = {"postID": str(self.shortcode_to_pk(code))}
        for name in self.RELAY_PROVIDERS:
            variables[f"__relay_internal__pv__{name}relayprovider"] = False
        return variables

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
                raise ThreadsAPIError(f"请求 Threads GraphQL 失败: {exc}") from exc

        if response.status_code != 200:
            raise ThreadsAPIError(f"Threads GraphQL 返回 HTTP {response.status_code}: {response.text[:500]}")

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            # 未登录时会返回 HTML 登录页
            raise ThreadsAPIError("Threads GraphQL 返回非 JSON 响应(可能需要登录)") from exc

        if payload.get("errors"):
            raise ThreadsAPIError(f"Threads GraphQL 返回错误: {payload['errors']}")
        return payload

    @staticmethod
    def _extract_post(payload: dict[str, Any], code: str) -> dict[str, Any] | None:
        data = ((payload.get("data") or {}).get("data")) or {}
        edges = data.get("edges") or []
        fallback: dict[str, Any] | None = None
        for edge in edges:
            for item in (edge.get("node") or {}).get("thread_items") or []:
                post = item.get("post")
                if not isinstance(post, dict):
                    continue
                if fallback is None:
                    fallback = post
                if post.get("code") == code:
                    return post
        # 找不到精确匹配时退回第一条 (通常即目标帖子本身)
        return fallback

    def _new_client(self) -> httpx.AsyncClient:
        cookies = self.DEFAULT_COOKIES | self.cookie
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.THREADS_URL,
            "User-Agent": UA,
            "X-IG-App-ID": self.X_IG_APP_ID,
        }
        return httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            proxy=self.proxy,
            timeout=self.timeout,
        )

    async def _ensure_csrf_token(self, client: httpx.AsyncClient) -> None:
        csrf_token = self._get_cookie_value(client, "csrftoken")
        if not csrf_token:
            try:
                await client.get(self.THREADS_URL, follow_redirects=True)
            except httpx.HTTPError as exc:
                raise ThreadsAPIError(f"获取 Threads csrftoken 失败: {exc}") from exc
            csrf_token = self._get_cookie_value(client, "csrftoken")
        if csrf_token:
            client.headers["x-csrftoken"] = csrf_token

    @staticmethod
    def _get_cookie_value(client: httpx.AsyncClient, name: str) -> str:
        values = [cookie.value for cookie in client.cookies.jar if cookie.name == name and cookie.value]
        return values[-1] if values else ""

    @classmethod
    def shortcode_to_pk(cls, code: str) -> int:
        pk = 0
        for ch in code:
            try:
                pk = pk * 64 + cls.SHORTCODE_ALPHABET.index(ch)
            except ValueError as exc:
                raise ValueError(f"无效的 Threads 帖子 ID: {code}") from exc
        return pk

    @staticmethod
    def get_username_by_url(url: str) -> str:
        u = re.search(r"/(@[\w.]+)/post/", url)
        if not u:
            raise ValueError("从 URL 中获取用户名失败")
        return u[1]

    @staticmethod
    def get_post_id_by_url(url: str) -> str:
        p = re.search(r"/post/([\w-]+)", url)
        if not p:
            raise ValueError("从 URL 中获取帖子 ID 失败")
        return p[1]


class ThreadsMediaType(Enum):
    IMAGE = "image"
    VIDEO = "video"


@dataclass
class ThreadsMedia:
    type: ThreadsMediaType
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0


@dataclass
class ThreadsPost:
    content: str
    media: ThreadsMedia | list[ThreadsMedia] | None = None

    @classmethod
    def from_graphql(cls, post: dict[str, Any]) -> ThreadsPost:
        caption = post.get("caption")
        content = caption.get("text") if isinstance(caption, dict) else caption
        return cls(content=str(content or ""), media=cls._fetch_media(post))

    @classmethod
    def _fetch_media(cls, d: dict[str, Any]) -> ThreadsMedia | list[ThreadsMedia]:
        media: ThreadsMedia | list[ThreadsMedia]
        match d.get("media_type"):
            case 1:  # 单张图片
                image = d["image_versions2"]["candidates"][0]
                media = ThreadsMedia(
                    type=ThreadsMediaType.IMAGE,
                    url=image["url"],
                    thumb_url=image["url"],
                    width=image.get("width", 0),
                    height=image.get("height", 0),
                )
            case 2:  # 单个视频
                thumb = d["image_versions2"]["candidates"][0]["url"]
                video = d["video_versions"][0]["url"]
                media = ThreadsMedia(
                    type=ThreadsMediaType.VIDEO,
                    url=video,
                    thumb_url=thumb,
                    width=d.get("original_width", 0),
                    height=d.get("original_height", 0),
                )
            case 8:  # 多图/视频
                media = []
                for m in d.get("carousel_media") or []:
                    if m.get("video_versions"):
                        thumb = m["image_versions2"]["candidates"][0]["url"]
                        media.append(
                            ThreadsMedia(
                                type=ThreadsMediaType.VIDEO,
                                url=m["video_versions"][0]["url"],
                                thumb_url=thumb,
                                width=m.get("original_width", 0),
                                height=m.get("original_height", 0),
                            )
                        )
                    else:
                        image = m["image_versions2"]["candidates"][0]
                        media.append(
                            ThreadsMedia(
                                type=ThreadsMediaType.IMAGE,
                                url=image["url"],
                                thumb_url=image["url"],
                                width=m.get("original_width", 0),
                                height=m.get("original_height", 0),
                            )
                        )
            case 19:  # 纯文本/外部链接
                linked = (d.get("text_post_app_info") or {}).get("linked_inline_media")
                media = cls._fetch_media(linked) if linked else []
            case _:
                media = []
        return media


__all__ = [
    "ThreadsAPI",
    "ThreadsAPIError",
    "ThreadsMedia",
    "ThreadsMediaType",
    "ThreadsPost",
]
