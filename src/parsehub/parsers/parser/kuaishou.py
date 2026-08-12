from loguru import logger

from ...provider_api.kuaishou import KuaiShouAPI, KuaishouParser
from ...types import ImageParseResult, ImageRef, ParseError, Platform, VideoParseResult, VideoRef
from ...utils.helpers import SecretCookie
from ..base.base import BaseParser

COOKIE = SecretCookie(
    "kpf=PC_WEB; clientid=3; did=web_bfbcdb2f5b3dc663a745deabafcf61e6; kwpsecproductname=kuaishou-"
    "vision; didv=1773330035000; kwpsecproductname=kuaishou-vision; userId=446442483; kuaishou.serv"
    "er.webday7_st=ChprdWFpc2hvdS5zZXJ2ZXIud2ViZGF5Ny5zdBKwAeuBbGjVcz39sj4G7d7P54r9C1etC_QftYb2I1X"
    "Mg01WSbw9NefL7E6EmwkYxHf70B9BM3Oyk20kFv1Y0xnRcfHtGNHYUHkmKguP6cvFeACofr2zPAZYRchRkndIBk5qExOl"
    "kr4FSoGpY-WqXeibapHNEbfZTLZl_QkQA4aGWotSZpBMv6wR3RxZWiMv60xc-CIndGICJbbRAaRGZNxz7QBj2Mr-SeU2o"
    "0bVi7esnD1AGhKquV16S9dezebl5ZuYo_R_JKgiIAidQF8n526Yos_GTgm3KrGknnEbkK-NMiNvTw3YBehZKAUwAQ; kua"
    "ishou.server.webday7_ph=f3720606882f1d7a76ab1ab52a489c4d44a1; bUserId=1000583835422; ktrace-c"
    "ontext=1|MS44Nzg0NzI0NTc4Nzk2ODY5Ljg3MTE4OTQ4LjE3NzM1NzExNTEyMjQuNDQ0OTc1MTI=|MS44Nzg0NzI0NTc4"
    "Nzk2ODY5LjUxNTU3MjM4LjE3NzM1NzExNTEyMjQuNDQ0OTc1MTM=|0|webservice-user-growth-node|webservice|"
    "true|src-Js; kwssectoken=BIjmefxxiTpXOdz9/RQ6Gl7cR5/0J7xaPzJ18udJgBSLTrJy4O7LhrYtbeeHGW+AOJrI6"
    "P8LQnioDWSuuQxV8Q==; kwscode=75d440673de879734b8700f363119968b4fabb4eb0369b1607e206d8e8c1ac9d;"
    " kpn=KUAISHOU_VISION; kwfv1=PnGU+9+Y8008S+nH0U+0mjPf8fP08f+98f+nLlwnrIP9P9G98YPf8jPBQSweS0+nr9"
    "G0mD8B+fP/L98/qlPe4f8eDI8f8jwBGh8BPAPfLEGALhGf+f+AYj+e4jPfLl+AY0G/cI+/Q0G0DEPfc98/mjw/pSPBbjGA"
    "rh8erl+ezfG/HlP0zf+0b0+n+DGnpj+0HI+9Qj+0p0PeDF+ADIPeL7+W==; kwssectoken=IMLS/eg005i6IUbIoIB/7W"
    "Byh8ciKMPUXULQ3a5/m3dK5D9ez8He/oMP2QLhil52v7Bk3O0CO2g6t5R/5XjSCw==; kwscode=75d440673de879734b"
    "8700f363119968b4fabb4eb0369b1607e206d8e8c1ac9d"
)


class KuaiShouParser(BaseParser):
    __platform__ = Platform.KUAISHOU
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?(www|v|live|v\.m)\.(kuaishou|chenzhongtech).com/.+"
    __redirect_keywords__ = ["v.kuaishou", "/f/"]

    async def _do_parse(self, raw_url: str) -> VideoParseResult | ImageParseResult:
        ksp = await KuaishouParser.create(
            raw_url, proxy=self.proxy, cookie=self.cookie.get_value() or COOKIE.get_value()
        )
        cover = ksp.get_cover_photo_url()
        if (
            ksp.page_type == "VIDEO" or "/short-video/" in raw_url
        ):  # 地区风控导致获取到的 page_type 可能为 ATLAS 但实际为视频
            try:
                content = ksp.get_title_content()
                video = ksp.get_real_video_url()
            except Exception as e:
                logger.error(f"快手 HTML 解析失败, 尝试 API 解析: {e}")
            else:
                if not video:
                    raise ParseError("-1 快手解析失败")

                return VideoParseResult(
                    title=content,
                    video=VideoRef(
                        url=video.url,
                        thumb_url=cover,
                        duration=video.d,
                        height=video.h,
                        width=video.w,
                    ),
                )

            ks = KuaiShouAPI(self.cookie.get_value() or COOKIE.get_value(), self.proxy)
            try:
                result = await ks.get_video_info(raw_url)
            except Exception as e:
                raise ParseError(f"-2 快手解析失败: {e}") from e
            else:
                return VideoParseResult(
                    title=result.title,
                    video=VideoRef(
                        url=result.video_url,
                        thumb_url=result.thumb_url,
                        duration=result.duration,
                        height=result.height,
                        width=result.width,
                    ),
                )
        else:
            content = ksp.get_title_content()
            img = ksp.get_image_list()
            if img:
                return ImageParseResult(
                    title=content, photo=[ImageRef(url=i.url, height=i.h, width=i.w, ext=i.e) for i in img]
                )
            if cover:
                return ImageParseResult(title=content, photo=[ImageRef(url=cover)])

            raise ParseError("快手解析失败 -3")


__all__ = ["KuaiShouParser"]
