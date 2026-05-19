import re
from collections.abc import Iterator
from typing import Any, NamedTuple

import requests
from instaloader import InstaloaderContext, InstaloaderException, Post


class MyPostSidecarNode(NamedTuple):
    is_video: bool
    display_url: str
    video_url: str | None
    width: int
    height: int


class MyPost(Post):
    def get_sidecar_nodes(self, start: int = 0, end: int = -1) -> Iterator[MyPostSidecarNode]:  # type: ignore[override]
        if self.typename == "GraphSidecar":
            edges = self._field("edge_sidecar_to_children", "edges")
            if end < 0:
                end = len(edges) - 1
            if start < 0:
                start = len(edges) - 1
            if any(edge["node"]["is_video"] and "video_url" not in edge["node"] for edge in edges[start : (end + 1)]):
                # video_url is only present in full metadata, issue #558.
                edges = self._full_metadata["edge_sidecar_to_children"]["edges"]
            for idx, edge in enumerate(edges):
                if start <= idx <= end:
                    node = edge["node"]
                    is_video = node["is_video"]
                    display_url = node["display_url"]
                    dimensions = node["dimensions"]
                    width = dimensions["width"]
                    height = dimensions["height"]

                    if not is_video and self._context.iphone_support and self._context.is_logged_in:
                        try:
                            carousel_media = self._iphone_struct["carousel_media"]
                            orig_url = carousel_media[idx]["image_versions2"]["candidates"][0]["url"]
                            display_url = re.sub(r"([?&])se=\d+&?", r"\1", orig_url).rstrip("&")
                        except (InstaloaderException, KeyError, IndexError) as err:
                            self._context.error(f"Unable to fetch high quality image version of {self}: {err}")
                    yield MyPostSidecarNode(
                        is_video=is_video,
                        display_url=display_url,
                        video_url=node["video_url"] if is_video else None,
                        width=width,
                        height=height,
                    )


class MyInstaloaderContext(InstaloaderContext):
    """
    支持自定义代理
    """

    def __init__(self, proxy: str | None = None, cookie: dict | None = None):
        self.proxy: dict[str, str | None] = {"http": proxy, "https": proxy}
        self.cookie = cookie
        super().__init__()

    def get_anonymous_session(self) -> requests.Session:
        session = super().get_anonymous_session()
        if self.proxy:
            session.proxies = {k: v for k, v in self.proxy.items() if v is not None}
            session.trust_env = False
        return session

    def get_json(self, *args: Any, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        if isinstance(session, requests.Session):
            if self.proxy:
                session.proxies = {k: v for k, v in self.proxy.items() if v is not None}
                session.trust_env = False
            if self.cookie:
                session.cookies.update(self.cookie)

        return super().get_json(*args, **kwargs)
