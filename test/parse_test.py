import asyncio

from loguru import logger
from src.parsehub.main import ParseHub
from src.parsehub.config import ParseConfig

test = {
    "bilibili": "https://www.bilibili.com/opus/1010846782483070978",
    "youtube": "https://youtube.com/shorts/uKV6Qtw1oGQ?si=Qhbh8Q2u7za7ow7o",
    "twitter": "https://x.com/alllisso_/status/1860043026162417790/photo/1",
    "douyin": "https://v.douyin.com/6BEYVNs",
    "tieba": "https://tieba.baidu.com/p/8985515891",
    "xhs": "https://www.xiaohongshu.com/explore/6687e378000000001e011b55?xsec_token=AB9JcyiuRPBS1JRdLr2rbBQD-xdm-zEWpS-tRoWoaWENw=",
    "facebook": "https://www.facebook.com/share/r/1FpXSkzHwe/",
    "weibo": "https://weibo.com/3208333150/Ow0iEbEX0",
    "tiktok": "https://www.tiktok.com/@norinpham_m4/video/7434865571910470913?is_from_webapp=1&sender_device=pc",
    "instagram": "https://www.instagram.com/p/DBOmTRESzd7/",
    "weixin": "https://mp.weixin.qq.com/s/rE6Dh_OzolgDTAh3ubM5KA",
}


@logger.catch
async def test_parse_hub():
    cfg = ParseConfig(douyin_api=None)
    ph = ParseHub(cfg)
    print("支持的平台: ", ph.get_supported_platforms())

    # for k, v in test.items():
    #     try:
    #         result = await ph.parse(v)
    #         print(f"{k}: {result}")
    #     except Exception as e:
    #         print(f"{k}: {e}")

    r = await ph.parse(test["bilibili"])
    print(r)
    # s = await r.summary()
    # print(s)


if __name__ == "__main__":
    asyncio.run(test_parse_hub())
