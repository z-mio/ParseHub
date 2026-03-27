import base64
import gzip
import hashlib
import json
import random
import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.base import Cipher
from cryptography.hazmat.primitives.ciphers.modes import CBC, ECB
from markdownify import MarkdownConverter


class XiaoHeiHePostType(Enum):
    VIDEO = "video"
    IMAGE = "image"  # 图文, 单张或多张图片 + 文案
    ARTICLE = "article"  # 文章, 文案中掺杂图片


class XiaoHeiHeMediaType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"


@dataclass
class XiaoHeiHeMedia:
    type: XiaoHeiHeMediaType
    url: str
    thumb_url: str | None = None
    height: int | None = None
    width: int | None = None


@dataclass
class XiaoHeiHePost:
    type: XiaoHeiHePostType
    title: str
    content: str = None
    media: list[XiaoHeiHeMedia] = None


class XiaoHeiHeAPI:
    def __init__(self, proxy: str | None = None):
        self.api_url = "https://api.xiaoheihe.cn"
        self.proxy = proxy

    async def parse(self, url):
        link_id = self.get_link_id(url)
        data = await self.link_tree(link_id)
        link = data["link"]

        title = link["title"]
        text = link["text"]

        is_video = link["has_video"]
        if is_video:
            post_type = XiaoHeiHePostType.VIDEO
            video_url = link["video_url"]
            video_thumb = link["video_thumb"]
            return XiaoHeiHePost(
                type=post_type,
                title=title,
                content=text,
                media=[XiaoHeiHeMedia(type=XiaoHeiHeMediaType.VIDEO, url=video_url, thumb_url=video_thumb)],
            )
        else:
            use_concept_type = link.get("use_concept_type", False)
            text_list = json.loads(text)
            if text_list[0]["type"] == "html":
                html = text_list[0]["text"]
                content = XHHConverter(heading_style="ATX").convert(html)
            else:
                content = text_list[0]["text"]
            post_type = XiaoHeiHePostType.IMAGE if use_concept_type else XiaoHeiHePostType.ARTICLE
            images = []
            for image in text_list[1:]:
                if image["type"] == "img":
                    media_type = XiaoHeiHeMediaType.GIF if ".gif" in image["url"] else XiaoHeiHeMediaType.IMAGE
                    images.append(
                        XiaoHeiHeMedia(
                            type=media_type,
                            url=image["url"],
                            thumb_url=image["url"],
                            height=int(float(image.get("height", 0))),
                            width=int(float(image.get("width", 0))),
                        )
                    )
            return XiaoHeiHePost(type=post_type, title=title, content=content, media=images)

    @staticmethod
    def get_link_id(url: str) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "link_id" in qs:
            return qs["link_id"][0]
        match = re.search(r"/link/([^/?]+)", parsed.path)
        if match:
            return match.group(1)
        raise ValueError(f"获取 link_id 失败: {url}")

    async def link_tree(self, link_id: str) -> dict:
        sig_params = XiaoHeiHeSign().sign("/bbs/app/link/tree")
        # sig_params = HeyBoxSigner().generate_signature("/bbs/app/link/tree")
        params = {
            "os_type": "web",
            "app": "heybox",
            "client_type": "web",
            "version": "999.0.4",
            "web_version": "2.5",
            "x_client_type": "web",
            "x_app": "heybox_website",
            "heybox_id": "",
            "x_os_type": "Windows",
            "device_info": "Chrome",
            "link_id": str(link_id),
            # 评论相关参数
            # "is_first": "1",
            # "page": "1",
            # "index": "1",
            # "limit": "20",
            "owner_only": "1",
            **sig_params,
        }
        cookies = {"x_xhh_tokenid": await SecuritySm.get_d_id()}
        async with httpx.AsyncClient(proxy=self.proxy) as cli:
            result = await cli.get(self.api_url + "/bbs/app/link/tree", params=params, cookies=cookies)
            result.raise_for_status()
            data = result.json()
        status = data.get("status")
        msg = data.get("msg")
        match status:
            case "ok":
                return data["result"]
            case "login":
                raise Exception(f"需要登录: {msg}")
            case "show_captcha":
                raise Exception("需要过验证码")
            case "relogin":
                raise Exception(f"需要重新登录: {msg}")
            case "failed":
                raise Exception(f"请求失败: {msg}")
            case "lack_token":
                raise Exception(f"缺少token: {msg}")
            case _:
                raise Exception(status)


class XiaoHeiHeSign:
    """
    小黑盒 API 签名生成器

    签名流程:
    1. 生成当前秒级时间戳 _time
    2. 生成随机 nonce（MD5(时间戳 + 随机数) 的大写形式）
    3. 根据 路径 + 时间戳 + nonce 通过 ov 算法计算 hkey
       - 三个输入分别经过字符映射后交织拼接，取前20位
       - MD5 后对头部和尾部分别做变换，拼接得到最终 hkey
    """

    # 字符映射表，用于将字符码映射为固定字符集中的字符
    CHAR_TABLE = "AB45STUVWZEFGJ6CH01D237IXYPQRKLMN89"

    # lv 对象中各 key 对应的时间戳偏移量
    # 运行时由 Wm[3] 决定使用哪个 key，当前为 "g" → offset = +1
    _OFFSET_MAP = {
        "a": -1,
        "b": -2,
        "c": -3,
        "d": -4,
        "e": -5,
        "f": 0,
        "g": +1,
        "h": +2,
        "i": +3,
        "j": +4,
        "k": +5,
    }

    def __init__(self, method_key: str = "g"):
        """
        Args:
            method_key: lv 对象的调度 key，决定时间戳偏移量，默认 "g"（即 Wm[3]）
        """
        self._offset = self._OFFSET_MAP[method_key]

    # ──────────────────── 公开接口 ────────────────────

    def sign(self, path: str) -> dict[str, str | int]:
        """
        为指定 API 路径生成签名参数

        Args:
            path: API 路径，如 "/bbs/app/link/tree"

        Returns:
            包含 hkey, _time, nonce 三个字段的字典
        """
        _time = int(time.time())

        # nonce = MD5(时间戳 + 随机小数).toUpperCase()
        nonce = hashlib.md5((str(_time) + str(random.random())).encode()).hexdigest().upper()

        hkey = self._ov(path, _time + self._offset, nonce)

        return {"hkey": hkey, "_time": _time, "nonce": nonce}

    # ──────────────────── 核心签名算法 ────────────────────

    def _ov(self, path: str, t: int, nonce: str) -> str:
        """
        核心签名计算

        Args:
            path:  标准化后的请求路径
            t:     经过偏移的时间戳
            nonce: 随机字符串
        """
        # Step 1: 路径标准化 → "/bbs/app/link/tree/"
        path = "/" + "/".join(p for p in path.split("/") if p) + "/"

        # Step 2: 对三组输入分别做字符映射
        #   - 时间戳字符串 → av 映射（映射表截掉末尾2位，长度34）
        #   - 路径          → sv 映射（映射表全量，长度36）
        #   - nonce         → sv 映射
        mapped = [
            self._av(str(t), self.CHAR_TABLE, -2),
            self._sv(path, self.CHAR_TABLE),
            self._sv(nonce, self.CHAR_TABLE),
        ]

        # Step 3: 三路交织拼接，取前 20 个字符
        interleaved = self._interleave(mapped)[:20]

        # Step 4: MD5
        md5_hex = hashlib.md5(interleaved.encode()).hexdigest()  # 32位十六进制

        # Step 5-a: 尾部 6 字符 → AES InvMixColumns → 求和 % 100
        tail_codes = [ord(c) for c in md5_hex[-6:]]
        mixed = self._mix_columns(tail_codes)
        suffix = str(sum(mixed) % 100).zfill(2)  # 补零到 2 位

        # Step 5-b: 头部 5 字符 → av 映射（映射表截掉末尾4位，长度32）
        prefix = self._av(md5_hex[:5], self.CHAR_TABLE, -4)

        return prefix + suffix  # 最终 hkey（7位字符串）

    # ──────────────────── 字符映射 ────────────────────

    @staticmethod
    def _av(text: str, table: str, cut: int) -> str:
        """
        按截断映射表替换字符

        对每个字符: table[charCode % len(截断后的table)]
        cut 为负数，表示从映射表末尾截掉 |cut| 个字符
        """
        sub_table = table[:cut]
        return "".join(sub_table[ord(c) % len(sub_table)] for c in text)

    @staticmethod
    def _sv(text: str, table: str) -> str:
        """
        按完整映射表替换字符

        对每个字符: table[charCode % len(table)]
        """
        return "".join(table[ord(c) % len(table)] for c in text)

    @staticmethod
    def _interleave(arrays: list[str]) -> str:
        """
        多路交织拼接（Round-Robin）

        依次从每个数组中取第 i 个字符拼接:
        ["ABC", "12", "XY"] → "A1X" + "B2Y" + "C" → "A1XB2YC"
        """
        result = []
        max_len = max(len(a) for a in arrays)
        for i in range(max_len):
            for a in arrays:
                if i < len(a):
                    result.append(a[i])
        return "".join(result)

    # ──────────────────── AES InvMixColumns ────────────────────
    # GF(2^8) 有限域运算，约减多项式 x^8 + x^4 + x^3 + x + 1 (0x1B)
    # 这组函数等价于 AES 的 InvMixColumns 变换矩阵乘法

    @staticmethod
    def _xtime(e: int) -> int:
        """GF(2^8) 上的 ×2 运算"""
        return (e << 1 ^ 27) & 0xFF if e & 128 else e << 1

    @classmethod
    def _mul3(cls, e: int) -> int:
        """GF(2^8) 上的 ×3 = ×2 ⊕ ×1"""
        return cls._xtime(e) ^ e

    @classmethod
    def _mul6(cls, e: int) -> int:
        """GF(2^8) 上的 ×6 = ×3(×2)"""
        return cls._mul3(cls._xtime(e))

    @classmethod
    def _mul12(cls, e: int) -> int:
        """GF(2^8) 上的 ×12 = ×6(×3(×2))"""
        return cls._mul6(cls._mul3(cls._xtime(e)))

    @classmethod
    def _mul14(cls, e: int) -> int:
        """GF(2^8) 上的 ×14 = ×12 ⊕ ×6 ⊕ ×3"""
        return cls._mul12(e) ^ cls._mul6(e) ^ cls._mul3(e)

    @classmethod
    def _mix_columns(cls, col: list[int]) -> list[int]:
        """
        AES InvMixColumns 变换

        输入: 至少 4 字节的列向量
        输出: 变换后的列向量（超出 4 个的元素原样追加）
        """
        # 确保至少有4个元素
        while len(col) < 4:
            col.append(0)

        e = col
        t = [
            cls._mul14(e[0]) ^ cls._mul12(e[1]) ^ cls._mul6(e[2]) ^ cls._mul3(e[3]),
            cls._mul3(e[0]) ^ cls._mul14(e[1]) ^ cls._mul12(e[2]) ^ cls._mul6(e[3]),
            cls._mul6(e[0]) ^ cls._mul3(e[1]) ^ cls._mul14(e[2]) ^ cls._mul12(e[3]),
            cls._mul12(e[0]) ^ cls._mul6(e[1]) ^ cls._mul3(e[2]) ^ cls._mul14(e[3]),
        ]

        # 额外元素原样追加
        if len(e) > 4:
            t.extend(e[4:])

        return t


class XHHConverter(MarkdownConverter):
    def convert_img(self, el, _, parent_tags):
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("data-original", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        if "_inline" in parent_tags and el.parent.name not in self.options["keep_inline_images_in"]:
            return alt

        return f"![{alt}]({src}{title_part})"


class SecuritySm:
    # FROM https://github.com/YueHen14/skyland-auto-sign/blob/6e7115b5580377c842f50f05b0fa39ab079c17b1/SecuritySm.py

    # 查询dId请求头
    DEVICES_INFO_URL = "https://fp-it.portal101.cn/deviceprofile/v4"

    # 数美配置
    SM_CONFIG = {
        "organization": "0yD85BjYvGFAvHaSQ1mc",
        "appId": "heybox_website",
        "publicKey": (
            "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCXj9exmI4nQjmT52iwr+yf7hAQ06bfSZHTAH"
            "UfRBYiagCf/whhd8es0R79wBigpiHLd28TKA8b8mGR8OiiI1hV+qfynCWihvp3mdj8MiiH6SU3"
            "lhro2hkfYzImZB0RmWr2zE4Xt1+A6Oyp6bf+W7JSxYUXHw3nNv7Td4jw4jEFKQIDAQAB"
        ),  # 小黑盒公钥
        "protocol": "https",
        "apiHost": "fp-it.portal101.cn",
    }

    PK = serialization.load_der_public_key(base64.b64decode(SM_CONFIG["publicKey"]))

    DES_RULE = {
        "appId": {"cipher": "DES", "is_encrypt": 1, "key": "uy7mzc4h", "obfuscated_name": "xx"},
        "box": {"is_encrypt": 0, "obfuscated_name": "jf"},
        "canvas": {"cipher": "DES", "is_encrypt": 1, "key": "snrn887t", "obfuscated_name": "yk"},
        "clientSize": {"cipher": "DES", "is_encrypt": 1, "key": "cpmjjgsu", "obfuscated_name": "zx"},
        "organization": {"cipher": "DES", "is_encrypt": 1, "key": "78moqjfc", "obfuscated_name": "dp"},
        "os": {"cipher": "DES", "is_encrypt": 1, "key": "je6vk6t4", "obfuscated_name": "pj"},
        "platform": {"cipher": "DES", "is_encrypt": 1, "key": "pakxhcd2", "obfuscated_name": "gm"},
        "plugins": {"cipher": "DES", "is_encrypt": 1, "key": "v51m3pzl", "obfuscated_name": "kq"},
        "pmf": {"cipher": "DES", "is_encrypt": 1, "key": "2mdeslu3", "obfuscated_name": "vw"},
        "protocol": {"is_encrypt": 0, "obfuscated_name": "protocol"},
        "referer": {"cipher": "DES", "is_encrypt": 1, "key": "y7bmrjlc", "obfuscated_name": "ab"},
        "res": {"cipher": "DES", "is_encrypt": 1, "key": "whxqm2a7", "obfuscated_name": "hf"},
        "rtype": {"cipher": "DES", "is_encrypt": 1, "key": "x8o2h2bl", "obfuscated_name": "lo"},
        "sdkver": {"cipher": "DES", "is_encrypt": 1, "key": "9q3dcxp2", "obfuscated_name": "sc"},
        "status": {"cipher": "DES", "is_encrypt": 1, "key": "2jbrxxw4", "obfuscated_name": "an"},
        "subVersion": {"cipher": "DES", "is_encrypt": 1, "key": "eo3i2puh", "obfuscated_name": "ns"},
        "svm": {"cipher": "DES", "is_encrypt": 1, "key": "fzj3kaeh", "obfuscated_name": "qr"},
        "time": {"cipher": "DES", "is_encrypt": 1, "key": "q2t3odsk", "obfuscated_name": "nb"},
        "timezone": {"cipher": "DES", "is_encrypt": 1, "key": "1uv05lj5", "obfuscated_name": "as"},
        "tn": {"cipher": "DES", "is_encrypt": 1, "key": "x9nzj1bp", "obfuscated_name": "py"},
        "trees": {"cipher": "DES", "is_encrypt": 1, "key": "acfs0xo4", "obfuscated_name": "pi"},
        "ua": {"cipher": "DES", "is_encrypt": 1, "key": "k92crp1t", "obfuscated_name": "bj"},
        "url": {"cipher": "DES", "is_encrypt": 1, "key": "y95hjkoo", "obfuscated_name": "cf"},
        "version": {"is_encrypt": 0, "obfuscated_name": "version"},
        "vpw": {"cipher": "DES", "is_encrypt": 1, "key": "r9924ab5", "obfuscated_name": "ca"},
    }

    BROWSER_ENV = {
        "plugins": (
            "MicrosoftEdgePDFPluginPortableDocumentFormatinternal-pdf-viewer1,Micros"
            "oftEdgePDFViewermhjfbmdgcfjbbpaeojofohoefgiehjai1"
        ),
        "ua": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
        ),
        "canvas": "259ffe69",  # 基于浏览器的canvas获得的值，不知道复用行不行
        "timezone": -480,  # 时区，应该是固定值吧
        "platform": "Win32",
        "url": "https://www.skland.com/",  # 固定值
        "referer": "",
        "res": "1920_1080_24_1.25",  # 屏幕宽度_高度_色深_window.devicePixelRatio
        "clientSize": "0_0_1080_1920_1920_1080_1920_1080",
        "status": "0011",  # 不知道在干啥
    }

    # 将浏览器环境对象的key全部排序，然后对其所有的值及其子对象的值加入数字并字符串相加。若值为数字，
    # 则乘以10000(0x2710)再将其转成字符串存入数组,最后再做md5,存入tn变量（tn变量要做加密）

    # 把这个对象用加密规则进行加密，然后对结果做GZIP压缩（结果是对象，应该有序列化），最后做AES加密（加密细节目前不
    # 清除），密钥为变量priId

    # 加密规则：新对象的key使用相对应加解密规则的obfuscated_name值，value为字符串化后进行进行DES加密，再进行btoa加密

    @classmethod
    def _DES(cls, o: dict):
        result = {}
        for i in o.keys():
            if i in cls.DES_RULE.keys():
                rule = cls.DES_RULE[i]
                res = o[i]
                if rule["is_encrypt"] == 1:
                    c = Cipher(TripleDES(rule["key"].encode("utf-8")), ECB())
                    data = str(res).encode("utf-8")
                    # 补足字节
                    data += b"\x00" * 8
                    res = base64.b64encode(c.encryptor().update(data)).decode("utf-8")
                result[rule["obfuscated_name"]] = res
            else:
                result[i] = o[i]
        return result

    @staticmethod
    def _AES(v: bytes, k: bytes):
        iv = "0102030405060708"
        key = AES(k)
        c = Cipher(key, CBC(iv.encode("utf-8")))
        c.encryptor()
        # 填充明文
        v += b"\x00"
        while len(v) % 16 != 0:
            v += b"\x00"
        return c.encryptor().update(v).hex()

    @staticmethod
    def GZIP(o: dict):
        # 这个压缩结果似乎和前台不太一样,不清楚是否会影响
        json_str = json.dumps(o, ensure_ascii=False)
        stream = gzip.compress(json_str.encode("utf-8"), 2, mtime=0)
        return base64.b64encode(stream)

    # 获得tn的值,后续做DES加密用
    @staticmethod
    def get_tn(o: dict):
        sorted_keys = sorted(o.keys())

        result_list = []

        for i in sorted_keys:
            v = o[i]
            if isinstance(v, (int, float)):
                v = str(v * 10000)
            elif isinstance(v, dict):
                v = SecuritySm.get_tn(v)
            result_list.append(v)
        return "".join(result_list)

    @staticmethod
    def get_smid():
        t = time.localtime()
        _time = f"{t.tm_year}{t.tm_mon:0>2d}{t.tm_mday:0>2d}{t.tm_hour:0>2d}{t.tm_min:0>2d}{t.tm_sec:0>2d}"
        uid = str(uuid.uuid4())
        v = _time + hashlib.md5(uid.encode("utf-8")).hexdigest() + "00"
        smsk_web = hashlib.md5(("smsk_web_" + v).encode("utf-8")).hexdigest()[0:14]
        return v + smsk_web + "0"

    @classmethod
    async def get_d_id(cls):
        uid = str(uuid.uuid4()).encode("utf-8")
        priId = hashlib.md5(uid).hexdigest()[0:16]
        ep = cls.PK.encrypt(uid, padding.PKCS1v15())
        ep = base64.b64encode(ep).decode("utf-8")

        browser = cls.BROWSER_ENV.copy()
        current_time = int(time.time() * 1000)
        browser.update({"vpw": str(uuid.uuid4()), "svm": current_time, "trees": str(uuid.uuid4()), "pmf": current_time})

        des_target = {
            **browser,
            "protocol": 102,
            "organization": cls.SM_CONFIG["organization"],
            "appId": cls.SM_CONFIG["appId"],
            "os": "web",
            "version": "3.0.0",
            "sdkver": "3.0.0",
            "box": "",  # 似乎是个SMID，但是第一次的时候是空,不过不影响结果
            "rtype": "all",
            "smid": cls.get_smid(),
            "subVersion": "1.0.0",
            "time": 0,
        }
        des_target["tn"] = hashlib.md5(cls.get_tn(des_target).encode()).hexdigest()

        des_result = cls._AES(cls.GZIP(cls._DES(des_target)), priId.encode("utf-8"))
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.DEVICES_INFO_URL,
                json={
                    "appId": "heybox_website",
                    "compress": 2,
                    "data": des_result,
                    "encode": 5,
                    "ep": ep,
                    "organization": cls.SM_CONFIG["organization"],
                    "os": "web",  # 固定值
                },
            )

        resp = response.json()
        if resp["code"] != 1100:
            raise Exception("did计算失败")
        # 开头必须是B
        return "B" + resp["detail"]["deviceId"]


if __name__ == "__main__":
    signer = XiaoHeiHeSign(method_key="g")
    result = signer.sign("/bbs/app/link/tree")
    print(result)
