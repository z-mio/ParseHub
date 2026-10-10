from ...provider_api.wxchannels import WXChannels, WXChannelsError
from ...types import ParseError, Platform, VideoParseResult, VideoRef
from ..base.base import BaseParser


class WXChannelsParser(BaseParser):
    __platform__ = Platform.WEIXIN_CHANNELS
    __supported_type__ = ["视频"]
    __match__ = (
        r"^(http(s)?://)?(weixin\.qq\.com/sph/\w+|"
        r"channels\.weixin\.qq\.com/finder-preview/pages/sph\?.*\bid=\w+)"
    )
    __reserved_parameters__ = ["id"]

    async def _do_parse(self, raw_url: str) -> VideoParseResult:
        cookie = self.cookie.get_value()
        if not cookie:
            raise ValueError("微信视频号需要配置腾讯元宝 (yuanbao.tencent.com) 登录 Cookie")

        cookie_text = "; ".join(f"{key}={value}" for key, value in cookie.items())
        try:
            video = await WXChannels(cookie=cookie_text, proxy=self.proxy).parse(raw_url)
        except WXChannelsError as e:
            raise ParseError(f"微信视频号解析失败: {e}") from e

        return VideoParseResult(title=video.title, video=VideoRef(url=video.video_url, thumb_url=video.thumb_url))


__all__ = ["WXChannelsParser"]
