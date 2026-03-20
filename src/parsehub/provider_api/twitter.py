import re
from dataclasses import dataclass
from typing import Literal, NamedTuple, Union

import httpx
from loguru import logger

from ..config import GlobalConfig
from ..types import ParseError


class Twitter:
    def __init__(self, proxy: str | None = None, cookie: dict = None):
        self.proxy = proxy
        self.authorization = (
            "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOu"
            "H5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
        )
        self.cookie = cookie

    async def fetch_tweet(self, url: str) -> "TwitterTweet":
        tweet_id = self.get_id_by_url(url)
        headers = {
            "accept-language": "zh-CN,zh;q=0.9",
            "authorization": self.authorization,
            "content-type": "application/json",
            "user-agent": GlobalConfig.ua,
            "x-guest-token": await self.get_guest_token(url),
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "zh-cn",
        }

        cookie = None
        if self.cookie and self.check_cookie():
            headers["x-csrf-token"] = self.cookie.get("ct0")
            cookie = self.cookie

        params = {
            "variables": f'{{"tweetId":"{tweet_id}","withComm'
            f'unity":false,"includePromotedContent":false,"withVoice":false}}',
            "features": '{"creator_subscriptions_tweet_preview_api_enabled":true,'
            '"communities_web_enable_tweet_community_results_fetch":true,'
            '"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,'
            '"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled"'
            ":true,"
            '"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,'
            '"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,'
            '"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled"'
            ":true,"
            '"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enable'
            'd":true,'
            '"tweet_with_visibility_results_prefer_gql_media_interstitial_enabled":false,"rweb_video_timestamps_enabled'
            '":true,'
            '"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,'
            '"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_'
            'phone_label_enabled":false,'
            '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"responsive_web_graphql_timeline'
            '_navigation_enabled":true,'
            '"responsive_web_enhance_cards_enabled":false}',
            "fieldToggles": '{"withArticleRichContentState":true,"withArticlePlainText":false}',
        }

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.get(
                "https://api.twitter.com/graphql/kPLTRmMnzbPTv70___D06w/TweetResultByRestId",
                params=params,
                headers=headers,
                cookies=cookie,
            )
        response.raise_for_status()
        return self.parse(response.json())

    def parse(self, result: dict):
        if e := result.get("errors"):
            raise Exception(f"error -1: {e[0]['message']}")

        result = result["data"]["tweetResult"].get("result")
        if not result:
            raise ParseError("error -4: 帖子或用户不存在")

        if tweet := result.get("tweet"):
            tweet_id = tweet.get("rest_id", {})
            legacy: dict = tweet.get("legacy")
        else:
            tweet_id = result.get("rest_id", {})
            legacy = result.get("legacy")

        if not legacy:
            if result.get("__typename") == "TweetTombstone":
                raise Exception("error -2: 该推文开启了限制, 匿名用户无法查看")
            raise Exception(f"error -3: {result.get('reason')}")

        if article := result.get("article", {}):
            ta = ArticleRenderer(article["article_results"]["result"]).render()
            return TwitterTweet(tweet_id=tweet_id, article=ta)

        if note_tweet := result.get("note_tweet"):
            full_text = note_tweet.get("note_tweet_results", {}).get("result", {}).get("text", None)
            if not full_text:
                full_text = legacy.get("full_text", "")
        else:
            full_text = legacy.get("full_text", "")

        media = legacy["entities"].get("media", [])
        media_list = []
        for i in media:
            original_info = i.get("original_info", {})
            height = original_info.get("height", 0)
            width = original_info.get("width", 0)
            media_url_https = i["media_url_https"]

            match i["type"]:
                case "photo":
                    media_list.append(
                        TwitterPhoto(
                            url=self._build_img_url(media_url_https, "orig"),
                            width=width,
                            height=height,
                            thumb_url=self._build_img_url(media_url_https, "small"),
                        )
                    )
                case "video":
                    video_info = i.get("video_info", {})
                    media_list.append(
                        TwitterVideo(
                            url=video_info["variants"][-1]["url"],
                            height=height,
                            width=width,
                            duration_millis=video_info.get("duration_millis", 0),
                            thumb_url=self._build_img_url(media_url_https, "medium"),
                        )
                    )
                case "animated_gif":
                    media_list.append(
                        TwitterAni(
                            url=i["video_info"]["variants"][-1]["url"],
                            height=height,
                            width=width,
                            thumb_url=self._build_img_url(media_url_https, "small"),
                        )
                    )

        return TwitterTweet(tweet_id=tweet_id, full_text=full_text, media=media_list or None)

    @staticmethod
    def _build_img_url(url: str, size: Literal["orig", "large", "medium", "small", "thumb"]):
        p = "&" if "?" in url else "?"
        return f"{url}{p}name={size}"

    @staticmethod
    def get_id_by_url(url: str):
        return re.search(r"status/(\d+)", url)[1]

    async def get_guest_token(self, url: str):
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.post(url)
            response.raise_for_status()
        guest_token = re.search(r'cookie="gt=(\d+);', response.text)
        if not guest_token:
            raise Exception("error -5: 获取 guest_token 失败")
        return guest_token[1]

    def check_cookie(self):
        if not self.cookie.get("ct0"):
            logger.warning("cookie 缺少必要参数: ct0")
            return False
        if not self.cookie.get("auth_token"):
            logger.warning("cookie 缺少必要参数: auth_token")
            return False
        return True


class TwitterTweet:
    def __init__(
        self,
        tweet_id: str,
        full_text: str | None = None,
        media: list[Union["TwitterVideo", "TwitterPhoto", "TwitterAni"]] | None = None,
        article: Union["TwitterArticle"] = None,
    ):
        self.tweet_id = tweet_id
        self.full_text = re.sub(r"https://t\.co/[^\s,]+$", "", full_text) if media else full_text
        self.media = media
        self.article = article


@dataclass
class TwitterArticle:
    title: str
    content: str
    media: list[Union["TwitterVideo", "TwitterPhoto"]] | None = None


@dataclass
class TwitterVideo:
    url: str
    height: int
    width: int
    duration_millis: int
    thumb_url: str | None = None


@dataclass
class TwitterPhoto:
    url: str
    height: int
    width: int
    thumb_url: str | None = None


@dataclass
class TwitterAni:
    url: str
    height: int
    width: int
    thumb_url: str | None = None


class _Insertion(NamedTuple):
    """待插入原文的 Markdown 标记。"""

    idx: int
    text: str
    kind: str  # "start" | "end" | "atomic"
    length: int = 0


class ArticleRenderer:
    """将 Twitter Article JSON 解析并渲染为 Markdown。"""

    # 行内样式 → Markdown 标记
    _INLINE_STYLES: dict[str, str] = {
        "Bold": "**",
        "Italic": "*",
        "Strikethrough": "~~",
    }

    # 块级类型 → 格式化函数
    _BLOCK_FORMATTERS: dict[str, callable] = {
        "header-one": lambda t: f"# {t}",
        "header-two": lambda t: f"## {t}",
        "header-three": lambda t: f"### {t}",
        "blockquote": lambda t: "\n".join(f"> {line}" for line in t.split("\n")),
        "ordered-list-item": lambda t: f"1. {t}",
        "unordered-list-item": lambda t: f"- {t}",
    }

    def __init__(self, article_data: dict):
        self._data = article_data
        self._media_dict: dict = {}
        self._media_result: list[TwitterPhoto | TwitterVideo] = []

    # ── 公共入口 ──────────────────────────────

    def render(self) -> "TwitterArticle":
        content_state = self._data.get("content_state", {})
        blocks = content_state.get("blocks", [])
        entity_map = {str(item["key"]): item["value"] for item in content_state.get("entityMap", [])}
        title = self._data.get("title", "")

        self._parse_media_entities()
        cover_url = self._data.get("cover_media", {}).get("media_info", {}).get("original_img_url", "")

        md_lines: list[str] = []
        if cover_url:
            md_lines.append(f"![Cover Image]({cover_url})\n")

        for block in blocks:
            md_lines.append(self._render_block(block, entity_map))

        return TwitterArticle(
            title=title,
            content="\n\n".join(md_lines),
            media=self._media_result or None,
        )

    # ── 媒体解析 ──────────────────────────────

    def _parse_media_entities(self) -> None:
        for media in self._data.get("media_entities", []):
            media_id = media.get("media_id")
            media_info = media.get("media_info", {})
            typename = media_info.get("__typename")

            if typename == "ApiImage":
                self._parse_image(media_id, media_info)
            elif typename == "ApiVideo":
                self._parse_video(media_id, media_info)

    def _parse_image(self, media_id, info: dict) -> None:
        url = info.get("original_img_url", "")
        if media_id and url:
            self._media_dict[media_id] = {"type": "image", "url": url}
        self._media_result.append(
            TwitterPhoto(
                url=url,
                height=info.get("original_img_height", 0),
                width=info.get("original_img_width", 0),
            )
        )

    def _parse_video(self, media_id, info: dict) -> None:
        preview = info.get("preview_image", {})
        preview_url = preview.get("original_img_url", "")
        video_url = self._best_mp4_url(info.get("variants", []))

        if media_id and preview_url:
            self._media_dict[media_id] = {
                "type": "video",
                "preview_url": preview_url,
                "video_url": video_url,
            }
        self._media_result.append(
            TwitterVideo(
                url=video_url,
                height=preview.get("original_img_height", 0),
                width=preview.get("original_img_width", 0),
                duration_millis=info.get("duration_millis", 0),
                thumb_url=preview_url,
            )
        )

    @staticmethod
    def _best_mp4_url(variants: list) -> str:
        mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
        if not mp4s:
            return ""
        return max(mp4s, key=lambda v: v.get("bit_rate", 0)).get("url", "")

    # ── Block 渲染 ────────────────────────────

    def _render_block(self, block: dict, entity_map: dict) -> str:
        b_type = block.get("type", "unstyled")
        text = block.get("text", "")

        insertions = self._collect_inline_styles(block)
        insertions += self._collect_entities(block, entity_map)
        insertions.sort(key=self._insertion_sort_key)

        final_text = self._apply_insertions(text, insertions)
        formatter = self._BLOCK_FORMATTERS.get(b_type)
        return formatter(final_text) if formatter else final_text

    @staticmethod
    def _collect_inline_styles(block: dict) -> list[_Insertion]:
        result: list[_Insertion] = []
        for style in block.get("inlineStyleRanges", []):
            marker = ArticleRenderer._INLINE_STYLES.get(style["style"])
            if not marker:
                continue
            offset, length = style["offset"], style["length"]
            result.append(_Insertion(offset, marker, "start", length))
            result.append(_Insertion(offset + length, marker, "end", length))
        return result

    def _collect_entities(self, block: dict, entity_map: dict) -> list[_Insertion]:
        result: list[_Insertion] = []
        for ent in block.get("entityRanges", []):
            offset, length = ent["offset"], ent["length"]
            ent_data = entity_map.get(str(ent["key"]), {})
            ent_type = ent_data.get("type")

            if ent_type == "LINK":
                url = ent_data.get("data", {}).get("url", "")
                result.append(_Insertion(offset, "[", "start", length))
                result.append(_Insertion(offset + length, f"]({url})", "end", length))

            elif ent_type == "MEDIA":
                md = self._media_entity_to_md(ent_data)
                if md:
                    result.append(_Insertion(offset, md, "atomic", length))

            elif ent_type == "DIVIDER":
                result.append(_Insertion(offset, "\n---\n", "atomic", length))

        return result

    def _media_entity_to_md(self, ent_data: dict) -> str:
        media_items = ent_data.get("data", {}).get("mediaItems", [])
        if not media_items:
            return ""
        obj = self._media_dict.get(media_items[0].get("mediaId"))
        if not obj:
            return ""

        if obj["type"] == "image":
            return f"![Image]({obj['url']})"
        if obj["type"] == "video":
            p, v = obj["preview_url"], obj["video_url"]
            return f"[![Video]({p})]({v})" if v else f"![Video Preview]({p})"
        return ""

    # ── 文本拼装 ──────────────────────────────

    @staticmethod
    def _insertion_sort_key(ins: _Insertion) -> tuple:
        weight = {"end": 1, "atomic": 0, "start": -1}.get(ins.kind, 0)
        return -ins.idx, weight, ins.length

    @staticmethod
    def _apply_insertions(text: str, insertions: list[_Insertion]) -> str:
        chars = list(text)
        for ins in insertions:
            if ins.kind == "atomic" and ins.idx < len(chars):
                chars[ins.idx] = ins.text
            else:
                chars.insert(ins.idx, ins.text)
        return "".join(chars)
