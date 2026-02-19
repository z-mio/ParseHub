import asyncio
import re
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import reduce
from hashlib import md5
from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
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

    async def get_dynamic_info(self, url: str, cookie: dict = None) -> "BiliDynamic":
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
                case 4101152:
                    raise Exception("动态不可见")
                case _:
                    raise Exception(f"获取动态信息失败: {mj}")
        return BiliDynamic.parse(data)

    async def get_video_info(self, url: str):
        """获取视频详细信息"""
        bvid = self.get_bvid(url)
        if not bvid:
            raise ValueError(f"Invalid url: {url}")
        response = await self._get_client().get(
            "https://api.bilibili.com/x/web-interface/view/detail",
            params={"bvid": bvid},
        )
        if response.status_code == 412:
            raise Exception("由于触发哔哩哔哩安全风控策略，该次访问请求被拒绝。")
        else:
            response.raise_for_status()
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


class DynamicType(Enum):
    """动态类型"""

    DYNAMIC_TYPE_FORWARD = "DYNAMIC_TYPE_FORWARD"  # 动态转发
    DYNAMIC_TYPE_DRAW = "DYNAMIC_TYPE_DRAW"  # 带图动态
    DYNAMIC_TYPE_AV = "DYNAMIC_TYPE_AV"  # 投稿视频
    DYNAMIC_TYPE_PGC_UNION = "DYNAMIC_TYPE_PGC_UNION"  # 剧集 (番剧、电影、纪录片)
    DYNAMIC_TYPE_WORD = "DYNAMIC_TYPE_WORD"  # 纯文字动态
    DYNAMIC_TYPE_ARTICLE = "DYNAMIC_TYPE_ARTICLE"  # 投稿专栏
    DYNAMIC_TYPE_MUSIC = "DYNAMIC_TYPE_MUSIC"  # 音乐
    DYNAMIC_TYPE_COMMON_SQUARE = "DYNAMIC_TYPE_COMMON_SQUARE"  # 装扮 / 剧集点评 / 普通分享
    DYNAMIC_TYPE_LIVE = "DYNAMIC_TYPE_LIVE"  # 直播间分享
    DYNAMIC_TYPE_MEDIALIST = "DYNAMIC_TYPE_MEDIALIST"  # 收藏夹
    DYNAMIC_TYPE_COURSES_SEASON = "DYNAMIC_TYPE_COURSES_SEASON"  # 课程
    DYNAMIC_TYPE_UGC_SEASON = "DYNAMIC_TYPE_UGC_SEASON"  # 合集更新
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


class MajorType(Enum):
    """动态主体类型"""

    MAJOR_TYPE_OPUS = "MAJOR_TYPE_OPUS"  # 图文动态
    MAJOR_TYPE_ARCHIVE = "MAJOR_TYPE_ARCHIVE"  # 视频
    MAJOR_TYPE_PGC = "MAJOR_TYPE_PGC"  # 剧集更新
    MAJOR_TYPE_MUSIC = "MAJOR_TYPE_MUSIC"  # 音频更新
    MAJOR_TYPE_COMMON = "MAJOR_TYPE_COMMON"  # 一般类型
    MAJOR_TYPE_LIVE = "MAJOR_TYPE_LIVE"  # 直播间分享
    MAJOR_TYPE_MEDIALIST = "MAJOR_TYPE_MEDIALIST"  # 收藏夹
    MAJOR_TYPE_COURSES = "MAJOR_TYPE_COURSES"  # 课程
    MAJOR_TYPE_UGC_SEASON = "MAJOR_TYPE_UGC_SEASON"  # 合集更新
    MAJOR_TYPE_UPOWER_COMMON = "MAJOR_TYPE_UPOWER_COMMON"  # 充电相关
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


@dataclass(kw_only=True)
class BiliImage:
    url: str
    width: int = 0
    height: int = 0
    live_url: str | None = None


@dataclass(kw_only=True)
class BiliDynamic:
    title: str | None = None
    content: str | None = None
    images: list[BiliImage] | None = None

    @classmethod
    def parse(cls, data: dict):
        module_dynamic: dict = data["item"]["modules"]["module_dynamic"]
        major: dict | None = module_dynamic.get("major", None)
        if not major:
            return cls._parse_forward(module_dynamic)
        else:
            return cls._parse_major(module_dynamic, major)

    @classmethod
    def _parse_major(cls, module_dynamic: dict, major: dict):
        major_type = major["type"]
        major_parsers: dict[MajorType, Callable[[dict, dict], BiliDynamic]] = {
            MajorType.MAJOR_TYPE_MEDIALIST: cls._parse_medialist,
            MajorType.MAJOR_TYPE_UPOWER_COMMON: cls._parse_upower_common,
            MajorType.MAJOR_TYPE_COMMON: cls._parse_common,
            MajorType.MAJOR_TYPE_OPUS: cls._parse_opus,
            MajorType.MAJOR_TYPE_ARCHIVE: cls._parse_av,
            MajorType.MAJOR_TYPE_PGC: cls._parse_pgc_union,
            MajorType.MAJOR_TYPE_LIVE: cls._parse_live,
            MajorType.MAJOR_TYPE_COURSES: cls._parse_courses,
            MajorType.MAJOR_TYPE_UGC_SEASON: cls._parse_ugc_season,
            MajorType.MAJOR_TYPE_MUSIC: cls._parse_music,
        }
        major_parser = major_parsers.get(MajorType(major_type), None)
        if not major_parser:
            raise ValueError(f"Unknown major type: {major_type}")
        return major_parser(module_dynamic, major)

    @classmethod
    def _parse_pgc_union(cls, _, major: dict):
        pgc = major["pgc"]
        return cls(title=pgc["title"], images=[BiliImage(url=pgc["cover"])])

    @classmethod
    def _parse_forward(cls, module_dynamic: dict):
        return cls(content=cls._get_desc_text(module_dynamic))

    @classmethod
    def _parse_av(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        archive = major["archive"]
        return cls(title=archive["title"], content=archive["desc"], images=cls._get_major_cover(archive))

    @classmethod
    def _parse_music(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        music = major["music"]
        return cls(title=music["title"], images=cls._get_major_cover(music))

    @classmethod
    def _parse_opus(cls, _, major: dict):
        opus = major["opus"]
        images = None
        if pics := opus["pics"]:
            images = [
                BiliImage(url=p["url"], live_url=p["live_url"], width=p["width"], height=p["height"]) for p in pics
            ]
        return cls(title=opus["title"], content=opus["summary"]["text"], images=images)

    @classmethod
    def _parse_common(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        common = major["common"]
        return cls(title=common["title"], content=common["desc"], images=cls._get_major_cover(common))

    @classmethod
    def _parse_live(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        live = major["live"]
        content = f"{live['desc_first']} · {live['desc_second']}" if live["desc_second"] else live["desc_first"]
        return cls(title=live["title"], content=content, images=cls._get_major_cover(live))

    @classmethod
    def _parse_medialist(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        medialist = major["medialist"]
        return cls(title=medialist["title"], content=medialist["sub_title"], images=cls._get_major_cover(medialist))

    @classmethod
    def _parse_courses(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        courses = major["courses"]
        content = f"{courses['sub_title']}\n\n{courses['desc']}" if courses["sub_title"] else courses["desc"]
        return cls(title=courses["title"], content=content, images=cls._get_major_cover(courses))

    @classmethod
    def _parse_ugc_season(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        ugc_season = major["ugc_season"]
        return cls(title=ugc_season["title"], content=ugc_season["desc"], images=cls._get_major_cover(ugc_season))

    @classmethod
    def _parse_upower_common(cls, module_dynamic: dict, major: dict):
        if content := cls._get_desc_text(module_dynamic):
            return cls(content=content)
        upower_common = major["upower_common"]
        title = (
            f"{upower_common['title_prefix']}: {upower_common['title']}"
            if upower_common["title_prefix"]
            else upower_common["title"]
        )
        return cls(title=title)

    @staticmethod
    def _get_desc_text(module_dynamic: dict) -> str | None:
        if desc := module_dynamic["desc"]:
            return desc["text"].strip()
        return None

    @staticmethod
    def _get_major_cover(major_content: dict) -> BiliImage | None:
        if major_content["cover"]:
            return BiliImage(url=major_content["cover"])
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
    r = asyncio.run(BiliAPI().get_dynamic_info("https://t.bilibili.com/1169207844562534435"))
    print(r)
