import re
from dataclasses import dataclass
from typing import Union

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
            "x-guest-token": await self.get_guest_token(),
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
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as he:
            raise Exception(f"http_status_{he.response.status_code}") from he
        return self.parse(response.json())

    @staticmethod
    def parse(result: dict):
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
            legacy: dict = result.get("legacy")

        if not legacy:
            if result.get("__typename") == "TweetTombstone":
                raise Exception("error -2: 该推文开启了限制, 匿名用户无法查看")
            raise Exception(f"error -3: {result.get('reason')}")

        if note_tweet := result.get("note_tweet"):
            full_text = note_tweet.get("note_tweet_results", {}).get("result", {}).get("text", None)
            if not full_text:
                full_text = legacy.get("full_text", "")
        else:
            full_text = legacy.get("full_text", "")

        media = legacy["entities"].get("media", [])
        medias = []
        for i in media:
            match i["type"]:
                case "photo":
                    medias.append(TwitterPhoto(url=i["media_url_https"]))
                case "video":
                    original_info = i.get("original_info", {})
                    medias.append(
                        TwitterVideo(
                            url=i["video_info"]["variants"][-1]["url"],
                            height=original_info.get("height", 0),
                            width=original_info.get("width", 0),
                        )
                    )
                case "animated_gif":
                    medias.append(TwitterAni(url=i["video_info"]["variants"][-1]["url"]))

        return TwitterTweet(tweet_id=tweet_id, full_text=full_text, media=medias)

    @staticmethod
    def get_id_by_url(url: str):
        return re.search(r"status/(\d+)", url)[1]

    async def get_guest_token(self):
        headers = {
            "Authorization": self.authorization,
        }
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.post("https://api.twitter.com/1.1/guest/activate.json", headers=headers)
        return response.json()["guest_token"]

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
        full_text: str,
        media: list[Union["TwitterVideo", "TwitterPhoto", "TwitterAni"]],
    ):
        self.tweet_id = tweet_id
        self.full_text = re.sub(r"https://t\.co/[^\s,]+$", "", full_text) if media else full_text
        self.media = media


@dataclass
class TwitterVideo:
    url: str
    height: int
    width: int


@dataclass
class TwitterPhoto:
    url: str


@dataclass
class TwitterAni:
    url: str
