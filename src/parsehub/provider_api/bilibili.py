import asyncio
import re
import time
import urllib.parse
from dataclasses import dataclass
from functools import reduce
from hashlib import md5
from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
XOR_CODE = 23442827791579
MASK_CODE = 2251799813685247
MAX_AID = 1 << 51
ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
ENCODE_MAP = 8, 7, 0, 5, 1, 3, 2, 4, 6
DECODE_MAP = tuple(reversed(ENCODE_MAP))

BASE = len(ALPHABET)
PREFIX = "BV1"
PREFIX_LEN = len(PREFIX)
CODE_LEN = len(ENCODE_MAP)


class BiliAPI:
    def __init__(self, proxy: str = None):
        self.headers = {"User-Agent": USER_AGENT}
        self.proxy = proxy
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def get_dynamic_info(self, url: str, cookie: dict = None) -> dict:
        """获取动态信息"""
        dyn_id = re.search(r"\b\d{18,19}\b", url).group(0)
        params = {
            "timezone_offset": "-480",
            "id": dyn_id,
            "features": "itemOpusStyle",
        }
        headers = self.headers.copy()
        headers |= {
            "referer": f"https://t.bilibili.com/{dyn_id}",
        }
        response = await self._get_client().get(
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail",
            headers=headers,
            params=params,
            cookies=cookie,
        )
        response.raise_for_status()
        mj = response.json()
        if not (data := mj.get("data")):
            match mj.get("code"):
                case -352:
                    raise Exception("获取动态信息失败: -352 风控限制")
                case _:
                    raise Exception(f"获取动态信息失败: {mj}")
        return data

    async def get_video_info(self, url: str):
        """获取视频详细信息"""
        bvid = self.get_bvid(url)
        response = await self._get_client().get(
            "https://api.bilibili.com/x/web-interface/view/detail",
            params={"bvid": bvid},
        )
        return response.json()

    async def get_video_playurl(self, url, cid, b3, b4, is_high_quality=True) -> dict:
        bvid = self.get_bvid(url)
        params = {
            "bvid": bvid,
            "cid": cid,
            "qn": 64 if is_high_quality else 16,  # 高画质为720p, 低画质为360p
            "fnver": 0,
            "fnval": 1,
            "fourk": 1,
            "gaia_source": "",
            "from_client": "BROWSER",
            "is_main_page": "false",
            "need_fragment": "false",
            "isGaiaAvoided": "true",
            "web_location": 1315873,
            "voice_balance": 1,
        }
        cookies = {
            "SESSDATA": "",
            "buvid3": b3,
            "buvid4": b4,
            "bili_jct": "",
            "ac_time_value": "",
            "opus-goback": "1",
        }
        response = await self._get_client().get(
            "https://api.bilibili.com/x/player/playurl",
            params=params,
            cookies=cookies,
        )
        return response.json()

    async def get_buvid(self):
        """获取 buvid"""
        response = await self._get_client().get(
            "https://api.bilibili.com/x/frontend/finger/spi",
        )
        data = response.json()
        return data["data"]["b_3"], data["data"]["b_4"]

    async def ai_summary(self, bvid: str) -> "AISummaryResult":
        bvid = self.av2bv(aid=bvid)
        info = await self.get_video_info(bvid)
        cid = info["data"]["View"]["cid"]
        up_mid = info["data"]["View"]["owner"]["mid"]
        wbi = await BiliWbiSigner().wbi(bvid=bvid, cid=cid, up_mid=up_mid)
        return await self.get_ai_summary(bvid, cid, up_mid, wbi["w_rid"], wbi["wts"])

    async def get_ai_summary(self, bvid: str, cid: int, up_mid: int, w_rid: str, wts: int):
        url = "https://api.bilibili.com/x/web-interface/view/conclusion/get"
        result = await self._get_client().get(
            url,
            params={
                "bvid": bvid,
                "cid": cid,
                "up_mid": up_mid,
                "w_rid": w_rid,
                "wts": wts,
            },
        )
        return AISummaryResult.parse(result.json())

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False):
            self._client = httpx.AsyncClient(proxy=self.proxy, headers=self.headers)
        return self._client

    async def aclose(self):
        if self._client is not None and not getattr(self._client, "is_closed", False):
            await self._client.aclose()
            self._client = None

    @staticmethod
    def av2bv(aid: str) -> str:
        if aid.upper().startswith("BV"):
            return aid
        aid = int(aid.removeprefix("av"))
        bvid = [""] * 9
        tmp = (MAX_AID | aid) ^ XOR_CODE
        for i in range(CODE_LEN):
            bvid[ENCODE_MAP[i]] = ALPHABET[tmp % BASE]
            tmp //= BASE
        return PREFIX + "".join(bvid)

    @staticmethod
    def bv2av(bvid: str) -> str:
        assert bvid[:3] == PREFIX

        bvid = bvid[3:]
        tmp = 0
        for i in range(CODE_LEN):
            idx = ALPHABET.index(bvid[DECODE_MAP[i]])
            tmp = tmp * BASE + idx
        return f"av{(tmp & MASK_CODE) ^ XOR_CODE}"

    def get_bvid(self, url: str):
        m_bv = re.search(r"BV[0-9A-Za-z]{10,}", url)
        if m_bv:
            return m_bv.group(0)
        m_av = re.search(r"(?i)\bav(\d+)\b", url)
        if m_av:
            return self.av2bv(f"av{m_av.group(1)}")
        return None


@dataclass
class PartOutline:
    timestamp: int
    content: str

    @staticmethod
    def parse(data: dict[str, Any]) -> "PartOutline":
        return PartOutline(timestamp=data["timestamp"], content=data["content"])


@dataclass
class Outline:
    title: str
    part_outline: list[PartOutline]
    timestamp: int

    @staticmethod
    def parse(data: dict[str, Any]) -> "Outline":
        part_outline = [PartOutline.parse(item) for item in data["part_outline"]]
        return Outline(title=data["title"], part_outline=part_outline, timestamp=data["timestamp"])


@dataclass
class ModelResult:
    result_type: int
    summary: str
    outline: list[Outline]

    @staticmethod
    def parse(data: dict[str, Any]) -> "ModelResult":
        if outline := data.get("outline"):
            outline = [Outline.parse(item) for item in outline]
        return ModelResult(result_type=data["result_type"], summary=data["summary"], outline=outline)


@dataclass
class Data:
    code: int
    model_result: ModelResult
    stid: str
    status: int
    like_num: int
    dislike_num: int

    @staticmethod
    def parse(data: dict[str, Any]) -> "Data":
        model_result = ModelResult.parse(data["model_result"])
        return Data(
            code=data["code"],
            model_result=model_result,
            stid=data["stid"],
            status=data["status"],
            like_num=data["like_num"],
            dislike_num=data["dislike_num"],
        )


@dataclass
class AISummaryResult:
    code: int
    message: str
    ttl: int
    data: Data | None

    @staticmethod
    def parse(json_dict: dict) -> "AISummaryResult":
        if data := json_dict.get("data"):
            data = Data.parse(data)
        else:
            data = None
        return AISummaryResult(
            code=json_dict["code"],
            message=json_dict["message"],
            ttl=json_dict["ttl"],
            data=data,
        )


class BiliWbiSigner:
    MIXIN_KEY_ENC_TAB = [
        46,
        47,
        18,
        2,
        53,
        8,
        23,
        32,
        15,
        50,
        10,
        31,
        58,
        3,
        45,
        35,
        27,
        43,
        5,
        49,
        33,
        9,
        42,
        19,
        29,
        28,
        14,
        39,
        12,
        38,
        41,
        13,
        37,
        48,
        7,
        16,
        24,
        55,
        40,
        61,
        26,
        17,
        0,
        1,
        60,
        51,
        30,
        4,
        22,
        25,
        54,
        21,
        56,
        59,
        6,
        63,
        57,
        62,
        11,
        36,
        20,
        34,
        44,
        52,
    ]

    def get_mixin_key(self, orig: str) -> str:
        """对 img_key 和 sub_key 进行字符顺序打乱编码"""
        return reduce(lambda s, i: s + orig[i], self.MIXIN_KEY_ENC_TAB, "")[:32]

    def sign_request_params(self, params: dict, img_key: str, sub_key: str) -> dict:
        """为请求参数进行 wbi 签名"""
        mixin_key = self.get_mixin_key(img_key + sub_key)
        params["wts"] = round(time.time())  # 添加 wts 字段
        params = {k: str(v) for k, v in sorted(params.items())}  # 按 key 排序并转为 str
        query = urllib.parse.urlencode(params, safe="!'()*")  # 序列化参数并指定不编码字符
        wbi_sign = md5((query + mixin_key).encode()).hexdigest()  # 计算 w_rid
        params["w_rid"] = wbi_sign
        return params

    @staticmethod
    async def fetch_wbi_keys() -> tuple[str, str]:
        """获取最新的 img_key 和 sub_key"""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    "https://api.bilibili.com/x/web-interface/nav",
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                json_data = resp.json()
                img_url: str = json_data["data"]["wbi_img"]["img_url"]
                sub_url: str = json_data["data"]["wbi_img"]["sub_url"]
            except httpx.HTTPError as e:
                raise Exception(f"请求 wbi_img 失败: {e}") from e
            except (KeyError, TypeError, ValueError) as e:
                raise Exception(f"解析 wbi_img 失败: {e}") from e

            img_key = img_url.rsplit("/", 1)[1].split(".")[0]
            sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
            return img_key, sub_key

    async def wbi(self, **kwargs) -> dict:
        img_key, sub_key = await self.fetch_wbi_keys()
        signed_params = self.sign_request_params(
            params={**kwargs},
            img_key=img_key,
            sub_key=sub_key,
        )
        return signed_params


if __name__ == "__main__":
    r = asyncio.run(BiliAPI().get_video_info("BV1Z4421U7LM"))
    print(r)
