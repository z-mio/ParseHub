import asyncio

from loguru import logger
from src.parsehub.main import ParseHub
from src.parsehub.config import ParseConfig

test = {
    "bilibili": "https://www.bilibili.com/video/BV1wbcdeWENh",
    "youtube": "https://www.youtube.com/watch?v=1h_uc3K4Cpg&list=RD1h_uc3K4Cpg&start_radio=1",
    "twitter": "https://x.com/alllisso_/status/1860043026162417790/photo/1",
    "douyin": "https://www.douyin.com/note/7489852932733685042",
    "tieba": "https://tieba.baidu.com/p/9401791338?frwh=index",
    "xhs": "https://www.xiaohongshu.com/explore/6687e378000000001e011b55?xsec_token=AB9JcyiuRPBS1JRdLr2rbBQD-xdm-zEWpS-tRoWoaWENw=",
    "facebook": "https://www.facebook.com/share/r/1FpXSkzHwe/",
    "weibo": "https://weibo.com/3208333150/Ow0iEbEX0",
    "tiktok": "https://www.tiktok.com/@norinpham_m4/video/7434865571910470913?is_from_webapp=1&sender_device=pc",
    "instagram": "https://www.instagram.com/napteazzz/reel/DH3QeWwzg5j/",
    "weixin": "https://mp.weixin.qq.com/s/7qseHCqY0bHk4_cgIcPe5g",
    "zuiyou": "https://share.xiaochuankeji.cn/hybrid/share/post?pid=393346270",
    "coolapk": "https://www.coolapk.com/picture/62144534?shareKey=YzAxMTNjNGY2ZWE4Njc4ZTQzZTA~&shareUid=3983969&shareFrom=com.coolapk.market_15.0.2",
}


@logger.catch
async def test_parse_hub():
    cfg = ParseConfig()
    ph = ParseHub(cfg)
    print("支持的平台: ", ph.get_supported_platforms())

    # for k, v in test.items():
    #     try:
    #         result = await ph.parse(v)
    #         print(f"{k}: {result}")
    #     except Exception as e:
    #         print(f"{k}: {e}")

    r = await ph.parse(test["youtube"])
    print(r)
    s = await r.download()
    print(s)
    # s.delete()


if __name__ == "__main__":
    asyncio.run(test_parse_hub())
