# mypy: disable-error-code=no-untyped-def
"""https://github.com/cv-cat/ZhihuApis
Pure-Python implementation of Zhihu's x-zse-96 (v2.0) signature algorithm.

This module reproduces, without Node.js / execjs, the encryption performed by
``static/zhihu.js`` + ``static/other.js``.

Pipeline (reverse engineered from the obfuscated bytecode VM in ``other.js``):

1. ``source = "+".join([zse93, path, d_c0, (body), (x_zst_81)])`` (empty parts skipped)
2. ``digest = md5(source)`` (32 hex chars)
3. ``plain  = ascii(digest[14:])`` padded with PKCS#7 to 32 bytes
4. ``cipher = SM4_CBC(plain, key=<fixed round keys>, iv=<random 16 bytes>)``
   (the SM4 key schedule is baked in as ``SM4_ZK``; ``SM4_ZB`` is the S-box)
5. ``blob   = iv + cipher`` (48 bytes; the IV is prepended so the server can decrypt)
6. ``sig    = custom_base64(blob)`` where the 384-bit stream is split into 64
   sextets, the sextet order is reversed and each sextet is XOR-ed with a fixed
   periodic mask, then mapped through a permuted alphabet.
7. ``x-zse-96 = "2.0_" + sig``

All constants below were extracted from the running JS and the mapping was
verified bit-exactly against 500 reference outputs.
"""

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self, cast
from urllib.parse import urlparse

import httpx

__all__ = ["get_x_zse_96", "ZhihuAPI", "ZhihuQA", "ZhihuZhuanLan", "ZhihuPin", "ZhihuPinType", "ZhihuMedia"]

from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter


class ZhihuConverter(MarkdownConverter):
    def convert_img(self, el: Any, text: Any, parent_tags: Any) -> str:
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("src", None) or ""
        if src.startswith("data:image/svg"):
            return alt
        # if '/equation' in src:
        #     parsed_url = urlparse(src)
        #     query_params = parse_qs(parsed_url.query)
        #     tex_value = query_params.get('tex', [''])[0]
        #     src = f"https://latex.codecogs.com/png.image?\\dpi{{200}}\\bg{{white}}{tex_value}"
        title = el.attrs.get("title", None) or ""
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        options = cast(dict[str, Any], getattr(self, "options"))  # noqa: B009
        if "_inline" in parent_tags and el.parent.name not in options["keep_inline_images_in"]:
            return alt

        return f"![{alt}]({src}{title_part})"


def _zhihu_contenc_fmt(content: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(content, "lxml")
    markdown_content = ZhihuConverter(heading_style="ATX").convert(str(soup))
    plaintext_content = "".join(BeautifulSoup(markdown(markdown_content), "lxml").find_all(string=True))
    imgs = [
        str(i["src"])
        for i in soup.find_all("img")
        if not str(i["src"]).startswith("data:image/svg") and "/equation" not in str(i["src"])  # 过滤掉 svg 和 equation
    ]
    return markdown_content, plaintext_content, imgs


@dataclass(kw_only=True)
class ZhihuQA:
    question: str
    imgs: list[str]
    markdown_answer: str | None = None
    plaintext_answer: str | None = None

    @classmethod
    def parse(cls, data: dict) -> Self:
        question = data["question"]["title"]
        answer = data["content"]
        markdown_content, plaintext_content, imgs = _zhihu_contenc_fmt(answer)
        return cls(question=question, imgs=imgs, markdown_answer=markdown_content, plaintext_answer=plaintext_content)


@dataclass(kw_only=True)
class ZhihuZhuanLan:
    title: str
    imgs: list[str]
    markdown_content: str | None = None
    plaintext_content: str | None = None

    @classmethod
    def parse(cls, data: dict) -> Self:
        title = data["title"]
        content = data["content"]
        markdown_content, plaintext_content, imgs = _zhihu_contenc_fmt(content)
        return cls(title=title, imgs=imgs, markdown_content=markdown_content, plaintext_content=plaintext_content)


class ZhihuPinType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"


@dataclass(kw_only=True)
class ZhihuMedia:
    url: str
    thumb_url: str | None = None
    width: int = 0
    height: int = 0
    duration: int = 0


@dataclass(kw_only=True)
class ZhihuPin:
    type: ZhihuPinType
    title: str
    media: list[ZhihuMedia]
    markdown_content: str | None = None
    plaintext_content: str | None = None

    @classmethod
    def parse(cls, result: dict) -> "ZhihuPin":
        content: list = result["content"]
        title = ""
        text = ""
        media = []
        t = ZhihuPinType.TEXT
        for c in content:
            match c["type"]:
                case "text":
                    title = c["title"]
                    text = c["content"]
                case "image":
                    t = ZhihuPinType.IMAGE
                    media.append(
                        ZhihuMedia(
                            url=c["original_url"],
                            thumb_url=c["url"],
                            width=c["width"],
                            height=c["height"],
                        )
                    )
                case "video":
                    t = ZhihuPinType.VIDEO
                    video_info = c["video_info"]
                    playlist: dict = video_info["playlist"]
                    v = list(playlist.values())[0]  # 画质从高到低, 0为最高
                    media.append(
                        ZhihuMedia(
                            url=v["url"],
                            thumb_url=video_info["thumbnail"],
                            width=v["width"],
                            height=v["height"],
                            duration=video_info["duration"],
                        )
                    )
        markdown_content, plaintext_content, imgs = _zhihu_contenc_fmt(text)
        return cls(
            title=title, media=media, markdown_content=markdown_content, plaintext_content=plaintext_content, type=t
        )


class ZhihuAPI:
    def __init__(self, cookie: dict[str, str], proxy: str | None = None):
        self.proxy = proxy
        self.cookie = cookie

    @property
    def d_c0(self) -> str:
        v = self.cookie.get("d_c0")
        if not v:
            raise ValueError("d_c0 is not found in cookie")
        return v

    @staticmethod
    def get_headers(x_zse_96: str) -> dict:
        return {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "origin": "https://zhuanlan.zhihu.com",
            "referer": "https://zhuanlan.zhihu.com/",
            "sec-ch-ua": '"Microsoft Edge";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
            ),
            "x-requested-with": "fetch",
            "x-zse-93": "101_3_3.0",
            "x-zse-96": x_zse_96,
        }

    async def parse(self, raw_url: str) -> ZhihuQA | ZhihuZhuanLan | ZhihuPin:
        if "/question" in raw_url:
            return await self.parse_qa(raw_url)
        if "zhuanlan." in raw_url:
            return await self.parse_zl(raw_url)
        if "/pin/" in raw_url:
            return await self.parse_pin(raw_url)
        raise ValueError("不支持的类型")

    async def parse_qa(self, raw_url: str) -> ZhihuQA:
        qid, aid = self._get_qa_id(raw_url)
        if aid:
            result = await self._answers(aid)
            return ZhihuQA.parse(result)
        result = await self._questions_answers(qid)
        data = result["data"]
        if data:
            result = await self._answers(data[0]["id"])
            return ZhihuQA.parse(result)
        result = await self._questions(qid)
        return ZhihuQA(question=result["title"], imgs=[])

    async def parse_zl(self, raw_url: str) -> ZhihuZhuanLan:
        zl_id = self._get_zl_id(raw_url)
        result = await self._zl(zl_id)
        return ZhihuZhuanLan.parse(result)

    async def parse_pin(self, raw_url: str) -> ZhihuPin:
        pin_id = self._get_pin_id(raw_url)
        result = await self._pin(pin_id)
        return ZhihuPin.parse(result)

    async def _questions(self, question_id: int | str) -> dict:
        """获取问题"""
        url = f"https://www.zhihu.com/api/v4/questions/{question_id}"
        query: dict = {}
        x_zse_96 = get_x_zse_96(url, query, self.d_c0)
        headers = self.get_headers(x_zse_96)

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=query, cookies=self.cookie)
            return dict(r.json())

    async def _questions_answers(self, question_id: int | str) -> dict:
        """获取问题的回答"""
        url = f"https://www.zhihu.com/api/v4/questions/{question_id}/answers"
        query = {
            "offset": "",
            "limit": "1",
            "sort_by": "default",
            "include": "data[*].content",
        }
        x_zse_96 = get_x_zse_96(url, query, self.d_c0)
        headers = self.get_headers(x_zse_96)

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=query, cookies=self.cookie)
            return dict(r.json())

    async def _answers(self, answers_id: int | str) -> dict:
        """获取问题的指定回答"""
        url = f"https://www.zhihu.com/api/v4/answers/{answers_id}"
        query = {
            "include": "data[*].content",
        }
        x_zse_96 = get_x_zse_96(url, query, self.d_c0)
        headers = self.get_headers(x_zse_96)

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=query, cookies=self.cookie)
            return dict(r.json())

    async def _zl(self, zl_id: int | str) -> dict:
        url = f"https://zhuanlan.zhihu.com/api/articles/{zl_id}"
        query: dict = {}
        x_zse_96 = get_x_zse_96(url, query, self.d_c0)
        headers = self.get_headers(x_zse_96)

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=query, cookies=self.cookie)
            return dict(r.json())

    async def _pin(self, pin_id: int | str) -> dict:
        url = f"https://www.zhihu.com/api/v4/pins/{pin_id}"
        query: dict = {}
        x_zse_96 = get_x_zse_96(url, query, self.d_c0)
        headers = self.get_headers(x_zse_96)

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=query, cookies=self.cookie)
            return dict(r.json())

    @staticmethod
    def _get_qa_id(raw_url: str) -> tuple[str, str | None]:
        """返回问题和回答 id,  没有回答 id 时返回 None"""
        r = re.search(r"/question/(\d+)(?:/answer/(\d+))?", raw_url)
        if not r:
            raise ValueError("从链接中提取 问答 id 错误")
        return r.group(1), r.group(2) if r.group(2) else None

    @staticmethod
    def _get_zl_id(raw_url: str) -> str:
        r = re.search(r"/p/(\d+)", raw_url)
        if not r:
            raise ValueError("从链接中提取 专栏 id 错误")
        return r.group(1)

    @staticmethod
    def _get_pin_id(raw_url: str) -> str:
        r = re.search(r"/pin/(\d+)", raw_url)
        if not r:
            raise ValueError("从链接中提取 圈子 id 错误")
        return r.group(1)


# --- SM4 constants (extracted from other.js VM) ---------------------------------
SM4_ZB = [
    20,
    223,
    245,
    7,
    248,
    2,
    194,
    209,
    87,
    6,
    227,
    253,
    240,
    128,
    222,
    91,
    237,
    9,
    125,
    157,
    230,
    93,
    252,
    205,
    90,
    79,
    144,
    199,
    159,
    197,
    186,
    167,
    39,
    37,
    156,
    198,
    38,
    42,
    43,
    168,
    217,
    153,
    15,
    103,
    80,
    189,
    71,
    191,
    97,
    84,
    247,
    95,
    36,
    69,
    14,
    35,
    12,
    171,
    28,
    114,
    178,
    148,
    86,
    182,
    32,
    83,
    158,
    109,
    22,
    255,
    94,
    238,
    151,
    85,
    77,
    124,
    254,
    18,
    4,
    26,
    123,
    176,
    232,
    193,
    131,
    172,
    143,
    142,
    150,
    30,
    10,
    146,
    162,
    62,
    224,
    218,
    196,
    229,
    1,
    192,
    213,
    27,
    110,
    56,
    231,
    180,
    138,
    107,
    242,
    187,
    54,
    120,
    19,
    44,
    117,
    228,
    215,
    203,
    53,
    239,
    251,
    127,
    81,
    11,
    133,
    96,
    204,
    132,
    41,
    115,
    73,
    55,
    249,
    147,
    102,
    48,
    122,
    145,
    106,
    118,
    74,
    190,
    29,
    16,
    174,
    5,
    177,
    129,
    63,
    113,
    99,
    31,
    161,
    76,
    246,
    34,
    211,
    13,
    60,
    68,
    207,
    160,
    65,
    111,
    82,
    165,
    67,
    169,
    225,
    57,
    112,
    244,
    155,
    51,
    236,
    200,
    233,
    58,
    61,
    47,
    100,
    137,
    185,
    64,
    17,
    70,
    234,
    163,
    219,
    108,
    170,
    166,
    59,
    149,
    52,
    105,
    24,
    212,
    78,
    173,
    45,
    0,
    116,
    226,
    119,
    136,
    206,
    135,
    175,
    195,
    25,
    92,
    121,
    208,
    126,
    139,
    3,
    75,
    141,
    21,
    130,
    98,
    241,
    40,
    154,
    66,
    184,
    49,
    181,
    46,
    243,
    88,
    101,
    183,
    8,
    23,
    72,
    188,
    104,
    179,
    210,
    134,
    250,
    201,
    164,
    89,
    216,
    202,
    220,
    50,
    221,
    152,
    140,
    33,
    235,
    214,
]
# Pre-expanded 32 SM4 round keys (already derived from the fixed encryption key).
SM4_ZK = [
    k & 0xFFFFFFFF
    for k in [
        1170614578,
        1024848638,
        1413669199,
        -343334464,
        -766094290,
        -1373058082,
        -143119608,
        -297228157,
        1933479194,
        -971186181,
        -406453910,
        460404854,
        -547427574,
        -1891326262,
        -1679095901,
        2119585428,
        -2029270069,
        2035090028,
        -1521520070,
        -5587175,
        -77751101,
        -2094365853,
        -1243052806,
        1579901135,
        1321810770,
        456816404,
        -1391643889,
        -229302305,
        330002838,
        -788960546,
        363569021,
        -1947871109,
    ]
]

# --- custom base64 constants (extracted / solved from other.js) -----------------
ALPHABET = "6fpLRqJO8M/c3jnYxFkUVC4ZIG12SiH=5v0mXDazWBTsuw7QetbKdoPyAl+hN9rgE"
# per-sextet XOR mask, period 16 groups, repeated 4 times over the 64 output chars
MASKS = [58, 0, 0, 0, 0, 40, 3, 0, 0, 0, 32, 14, 0, 0, 0, 0] * 4

ZSE93 = "101_3_3.0"


def _u32(x):
    return x & 0xFFFFFFFF


def _rotl(x, n):
    return _u32((x << n) | (x >> (32 - n)))


def _load_be(arr, o):
    return _u32((arr[o] << 24) | (arr[o + 1] << 16) | (arr[o + 2] << 8) | arr[o + 3])


def _store_be(v, arr, o):
    arr[o] = (v >> 24) & 255
    arr[o + 1] = (v >> 16) & 255
    arr[o + 2] = (v >> 8) & 255
    arr[o + 3] = v & 255


def _tau_l(x):
    b = [(x >> 24) & 255, (x >> 16) & 255, (x >> 8) & 255, x & 255]
    t = [SM4_ZB[b[0]], SM4_ZB[b[1]], SM4_ZB[b[2]], SM4_ZB[b[3]]]
    ec = _load_be(t, 0)
    return _u32(ec ^ _rotl(ec, 2) ^ _rotl(ec, 10) ^ _rotl(ec, 18) ^ _rotl(ec, 24))


def _sm4_encrypt_block(block):
    out = [0] * 16
    x = [0] * 36
    x[0] = _load_be(block, 0)
    x[1] = _load_be(block, 4)
    x[2] = _load_be(block, 8)
    x[3] = _load_be(block, 12)
    for i in range(32):
        x[i + 4] = _u32(x[i] ^ _tau_l(x[i + 1] ^ x[i + 2] ^ x[i + 3] ^ SM4_ZK[i]))
    _store_be(x[35], out, 0)
    _store_be(x[34], out, 4)
    _store_be(x[33], out, 8)
    _store_be(x[32], out, 12)
    return out


def _sm4_cbc(data, iv):
    result = []
    prev = list(iv)
    for off in range(0, len(data), 16):
        block = data[off : off + 16]
        xored = [block[i] ^ prev[i] for i in range(16)]
        prev = _sm4_encrypt_block(xored)
        result.extend(prev)
    return result


def _pkcs7(data, block=16):
    pad = block - (len(data) % block)
    return list(data) + [pad] * pad


def _custom_b64(blob):
    # 48 bytes -> 384 bits -> 64 sextets
    bits = []
    for b in blob:
        for j in range(8):
            bits.append((b >> (7 - j)) & 1)
    in_sext = []
    for k in range(64):
        v = 0
        for j in range(6):
            v = (v << 1) | bits[6 * k + j]
        in_sext.append(v)
    out = []
    for g in range(64):
        out.append(ALPHABET[in_sext[63 - g] ^ MASKS[g]])
    return "".join(out)


def zhihu_encrypt(digest, iv=None):
    """Encrypt a 32-char md5 hex string, returning the base64 signature body.

    ``iv`` (16 bytes) is prepended to the ciphertext; the server recovers it, so
    any value works. Defaults to random bytes to mimic the browser.
    """
    if iv is None:
        iv = list(os.urandom(16))
    else:
        iv = list(iv)
    plain = _pkcs7([ord(c) for c in digest[14:]])
    cipher = _sm4_cbc(plain, iv)
    return _custom_b64(iv + cipher)


def encrypt_md5(source, iv=None):
    """md5(source) then encrypt -> signature body (without the ``2.0_`` prefix)."""
    digest = hashlib.md5(source.encode("utf-8")).hexdigest()
    return zhihu_encrypt(digest, iv=iv)


def get_x_zse_96(url, params, d_c0, body="", x_zst_81=None, iv=None):
    """Compute the full ``x-zse-96`` header value (pure Python, no Node)."""
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        er = url + "?" + query
    else:
        er = url
    parsed = urlparse(er)
    path = parsed.path + (("?" + parsed.query) if parsed.query else "")
    parts = [ZSE93, path, d_c0]
    if body:
        parts.append(body)
    if x_zst_81:
        parts.append(x_zst_81)
    source = "+".join(parts)
    return "2.0_" + encrypt_md5(source, iv=iv)


if __name__ == "__main__":

    async def main() -> None:
        cookies = ""
        cookie = {i.split("=")[0]: "=".join(i.split("=")[1:]) for i in cookies.split("; ")}
        zhihu = ZhihuAPI(cookie=cookie)
        print(await zhihu.parse("https://www.zhihu.com/pin/2052700331017080947"))

    asyncio.run(main())
