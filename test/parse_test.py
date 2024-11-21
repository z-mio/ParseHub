import asyncio

from loguru import logger
from src.parsehub.main import ParseHub
from src.parsehub.config import ParseConfig

test = {
    "bilibili": "https://www.bilibili.com/video/BV1NgUZYAEsW",
    "youtube": "https://www.youtube.com/watch?v=KfOEabr38WU",
    "twitter": "https://twitter.com/aobuta_anime/status/1827284717848424696",
    "douyin": "https://v.douyin.com/6BEYVNs",
    "tieba": "https://tieba.baidu.com/p/8985515891",
    "xhs": "https://www.xiaohongshu.com/explore/6687e378000000001e011b55?xsec_token=AB9JcyiuRPBS1JRdLr2rbBQD-xdm-zEWpS-tRoWoaWENw=",
    "facebook": "https://www.facebook.com/share/v/KrPrU7A8Jf4i1TxE/",
    "weibo": "https://weibo.com/3208333150/Ow0iEbEX0",
    "tiktok": "https://www.tiktok.com/@norinpham_m4/video/7434865571910470913?is_from_webapp=1&sender_device=pc",
    "instagram": "https://www.instagram.com/p/DCO54VhStTf/",
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

    r = await ph.parse(test["tieba"])
    print(r)
    s = await r.summary()
    print(s)


if __name__ == "__main__":
    asyncio.run(test_parse_hub())
