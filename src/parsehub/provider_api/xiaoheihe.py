import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter

V4_EP = (
    "V1ZCERzVgMWrKv+VcTl5QmS9JuPWLOQ8A0mACeTyYXtTbiguOrHhwaqnagZ6zdAgF"
    "4WpAYBvUH3EDnPRlNWut4CTDU1tCa80BSnvTMC9X1j9Kh6IMlGmzPIqpBzzx9r7Nt"
    "9XtUhv2WiQ2BgPnUwOFe7gN9r8Yj3184qxn1btJL8="
)
V4_DATA = (
    "abbbe96a1579aa6fe4fa84e875851b7d7a843a14c5c9573c771d9c1443c9b3a"
    "d7603a8d9d67dbc9bd001bf42702ac82e4a6979323ff305eecd74b9620ee140"
    "0c135f840b35d9402ec3e3a93fcb3d0d3d6b3e740f5176b72225b6fb8a0d483"
    "cab753aa71062dc9b59bc8de950628f23607301c6cd94e75f680b86485a11ac"
    "36eba1413e9f14b274eadff30114dfb1cedadc4bd08ef83c5b2d048970d07d3"
    "943afef809b44e3b9fee602c91e274fee1523a8beee7e7cec85680b279d616d"
    "da15e98b1b0aa718276bcdb05d4ac3e44e72da220e0ea798ad7452aec01d0db"
    "c31ad6bf147eab7f7e539d35fe5149110aae5c7069a67eba4aae638505819f8"
    "9e2a58bc3b5001c8a5045334121ef04a8e442d7dbb7776bd6013674d2c0028a"
    "f131bf6bde47b90dce5c8b9463c9f83d0e7264145c2f6f259d70c4d63a4996b"
    "b7c0074e8a59fa298ad144ec139cb29bc94074fbe2f4a88400d85c003793e2b"
    "e2077184c3ba2e792926fce25f24d3a764a7c2667446173c74aa704d0d517f2"
    "10926aaef05376230b43c3a676dad6ff1c9603553d66eadfb492445eac44745"
    "acc620b325560d4941c10e05f3099a17a553fd763a1b7d6ef29f512e436bdfa"
    "9fa7c5a70b6a5f91bbcb21946fc2ce92db0c92930008b0fc82e90c3c73f9265"
    "2ca388f77b262a918cf59160fa88e481138ee7fe9a9b51d7949a74d22d1dab4"
    "e865c12325bfb5b9e748526afb6d8a05c543fd6dc72e81b06a4ebbf8149fca5"
    "37a19330da2011eec0229e2302babe239397aa1c2292ab3807cf0aa129d078a"
    "a9da010003eac5bb2c06435fbbe9bee7543290c1224745bb485d78f42ee4e82"
    "afb27a38befc60a688fb2514795064926bf205357bd46b7c14dd15aea2cab48"
    "5c993f0df5a20811d0a7b3bfb1fcb0737c8305675e9bdac396ef8cffb0b6bc4"
    "700c3d881c1945329b721b9080bed46b18105b7c9fea4f8276f0fcd09fe99ec"
    "52fa50b11e12a19eb9d091ecde701ab2879e2d7727386b28bbde8d62832e1ad"
    "822ea57b383cdd3767e8ee64e201bf00fe9cc8428ece3262550764fea47c69e"
    "e4339de98767f034d8852993fdefa315d9dcda71a74b665804706d4f9a8c139"
    "3670c2220e4ceac833620e0dc8175eb7a77b8b37c1a9d9940c67d44c8bc6b5f"
    "9e46273e2f5149d3d3148e8f7a02c4a4c3c998924b7d0e93528952034adc20d"
    "c342404a8606f0c07cb2b98c4a5434e69b69282daf952f586b9eed4b4f1ef0c"
    "fe5c6d156d14fb5057c8c32a355d07e2f56737d1ccfad573d42c840bbe8b750"
    "388211f2c0c5d6a1e34e7741389a742dff58bb0b9f339707a349a09519ca78d"
    "5e4f1baaf2598ab9001c15824494eecc17735e69a193e5437cbe44c6f156a0b"
    "b8df4fed5edefd4f56f4ef0b4d8cc40fe623836da3c5e662005825c9d344074"
    "be2306d6241c163fe92a6ce40ff60538d7464f5a06b6bb9ca1e6f18491ca3c7"
    "d6c00e299cbb1ca1c525a981fc6c6f2bb05f709101099b8bd0d2c2a628d94c6"
    "1aa97fdd58c9f357359fbd5be9e8f0f534f4481fb780d58e3e599e01fdd5a7f"
    "c5fb7e01b76fd58b2f264947d2149fefa57577ef326e264fc827939329031d9"
    "01be7579ecf5fccdab11c615c1a053f198297c0723faf8b17ea3335d49df2bf"
    "dd17271c2b64745b1f412d87297edd4404a4ae5312debf73b66afcc3d884b93"
    "8de41b6ee87265ce624897f3557ebe2d97e6fb17f1dc6a893e48dfa16ef2bff"
    "d8f3e06f0a1fcf44c7f2efa372e0ff61344c93f4a2a66538fcc134cd0bf94d5"
    "4c969cda4392af70608cbab6cfa340b674ba3a59385c0ed9bb236ff6ed10e1e"
    "5a9d4b6529c075dc1ac23cfdae18ab1651a5ee747322e51e3cc6035ca929789"
    "00924e661a2694a47873569baa95fd821711dc53a1e0299ed707e337b570591"
    "a3f61a5e39f8a75771da1613e8236c9b1b94cb5617fdaf2424d68a7fbd83ebf"
    "356fc87e8a805bee5bbd20a55a70881394d7624b1dcf5a135f1cf40b842eca3"
    "3d46b72447e0a2e85adf6c26efa6cc73b63573840f7b6229fb03ab45a8b639b"
    "5a66bbd6f63d10e59db49d7a9c9af3e3aeb79b7b756e24d5002917e7e788018"
    "4f80fcc605a1ba825c779e6083fd7fb0920bbcee021ec8e35427391b871b149"
    "c306c2dbda602044cd53ec424dd70cfd1c14a23c9964c039258cff4b75112f8"
    "15d9717433c1989ec398cd2acd67c89be82a409e0ef8f3e9ea8ec8b51b5ea5a"
    "005b5e735978d9a2987a76d62a2af230e30dc6327f7c0d153add27c7e8a320e"
    "4df6c05ab91fe0b9f6f9e13c50f39454066776503eb2ec84b74b4b2d5228627"
    "d81c938f7201610c9b703e4fd283a94835b7387db2880443a050d3eb0859aa1"
    "efd0f9bb7613b6b918ec2f7b5bb3e7722105b595e7973a93e3de8153a0f8e5b"
    "fd1aa6cefc6285fea85e8381ddcce98b31dda33db2a3c80ac04df14b872c805"
    "15373f231c3653fb2db799b32e83e59fb0f5763febca3d291b49bf83dd7ebd6"
    "1229300b65d44964d9e679f6061a0b2ea1bcd9f5af9bf710047237d87d13394"
    "ea8b4627c6997589d0b58379d025b076460eab88d6615ee92b0aa6c47f721f9"
    "7e0b5bbe721f06544d0a1bb81402697f2d72ad32c791dab45064b4d18460602"
    "9494b268feaebb268e7f92352dc3482f857c14885aabbad98a43e5f8fa5d77d"
    "61dc22f23080b9e6403c76f5fb862d7520ab85ae7c1d0e339729f664e7d668f"
    "4b9d1301acabb62fda5940db236ea9d2ca896cbb6a13eda6120fa5881453cb4"
    "490438460c00db4cd4bdf5df993d3a8d5726c756015eed542e0a4b910570f39"
    "7211c3f84f6a0d038e82270f94543e8da1e8d0cffd8f4f561daaf6003ad1fad"
    "fdd89c50f057a79225d8647aead74b33216e328c4204686b4ae93ce5f7ee25e"
    "1c83fe2cb72c67589aa4865d278ff7a112d09c16707de8acd61b49b901a3266"
    "e8ef55f1351fdc3013154635e51e649cbf31fc9b32f6956800834ca73e0b75b"
    "2b54d7125257eb6c24ebff52b741109be6da99bb6e0ffab85c3c219550ec3fc"
    "b12e2e4d0234627b061193c290baa1be73241be70925c08d33e6efdd44eca9a"
    "5160bdc5b47bd1f9d3f2cbf38848cf1aaa2a4827f86e43e06246b3bf94cb0b9"
    "f050c89533a3be9ffecefebd1a92e04197f18d7fadc0bfc8664de18425d5c03"
    "59b58049267934756f513bd68ea427b38f15213f42cce05cd59f5ea502967ec"
    "6a096daaa5e5d2a373227f2fe4514e27dfa012d708f7e94a286452972b5fab4"
    "581ecee3df40bad802cbb50b1a5d9dd3323a5f7c61ab893b16782a0ba64fd42"
    "10c30ac00f9d21b9124e5e5b323f43badf56761e1eea5c86ff61f19ce1485f4"
    "2cf6cadd751bbfb2ef87229eee5068ef6e209f123d29a571a374974ceac2e77"
    "f143faba60fc5d16f88d801fa01d879420b5d1393ad5b2bc913e3b0ba7155a6"
    "7648196573126273cccc79f2eac32ab68d72cc0f7170feca9c9726af9d65962"
    "663d5281372386ec88bd2fa82316f687535ecd39f00658523708ca4785529f5"
    "93baf100597ed00c15ae8ff87baa295871680b4096ac03a550f0f015297198b"
    "1a93f38cfefbeceabc099c1026664d77f616b4f069cf8bf53d2684b9a4d933c"
    "3c65a3aef21559527bfc6586e0247efa244a0a355b43751bc09be8012699468"
    "a8c332d60b11bb4881bf56b92ead10e059ac40f83a4d6725cacbc1bb307c839"
    "c4edc8b5484b9e2935842e867e739223f2eaaaff04d9701cfa49e3f80be4f2d"
    "1b7e8eb76fd7f33dfa79831f75ee65a75b7c7fff98254818f1ab77bca856656"
    "4d48e0012733dd426bf841f27f960394b1bacb8a3e36b96c41d751584cd580f"
    "ef1b6a8bf990487268348f682a27549ecbb9674b14f2fc97f203f3468f248ec"
    "3cf5171aa5e8a8d31a9a433c4f7644736aaf6695b28771fe66b4736e3afb322"
    "11ad534b05641600d2cdc79a251fc4c4e5540df9a40aaad329fedd49a429b20"
    "70e1345a4146c297ee2a03f056675054e83207d17de21242032c30398259440"
    "84e60cbd70eb4c469859824cd7d04340de0d19e614a0826a63c63e15c3372b1"
    "7515d4b6951ff6c612f65c3e6538fd0515bcb4814bb641fca5a45c7dae9"
)


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
    markdown_content: str | None = None
    text_content: str = None
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
                text_content=text,
                markdown_content=text,
                media=[XiaoHeiHeMedia(type=XiaoHeiHeMediaType.VIDEO, url=video_url, thumb_url=video_thumb)],
            )
        else:
            use_concept_type = link.get("use_concept_type", False)
            text_list = json.loads(text)
            if text_list[0]["type"] == "html":
                html = text_list[0]["text"]
                markdown_content = MarkdownConverter(heading_style="ATX").convert(html)
                text_content = "".join(BeautifulSoup(markdown(markdown_content), "lxml").find_all(string=True))
            else:
                text_content = text_list[0]["text"]
                markdown_content = text_content
            post_type = XiaoHeiHePostType.IMAGE if use_concept_type else XiaoHeiHePostType.ARTICLE
            images = []
            for image in text_list[1:]:
                if image["type"] == "img":
                    media_type = (
                        XiaoHeiHeMediaType.GIF if image.get("text", "").endswith(".gif") else XiaoHeiHeMediaType.IMAGE
                    )
                    images.append(
                        XiaoHeiHeMedia(
                            type=media_type,
                            url=image["url"],
                            thumb_url=image["url"],
                            height=image["height"],
                            width=image["width"],
                        )
                    )
            return XiaoHeiHePost(
                type=post_type, title=title, text_content=text_content, markdown_content=markdown_content, media=images
            )

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
        cookies = {"x_xhh_tokenid": await self.fetch_x_xhh_tokenid()}
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

    async def v4(self):
        json_data = {
            "appId": "heybox_website",
            "organization": "0yD85BjYvGFAvHaSQ1mc",
            "ep": V4_EP,
            "data": V4_DATA,
            "os": "web",
            "encode": 5,
            "compress": 2,
        }
        async with httpx.AsyncClient(proxy=self.proxy) as cli:
            result = await cli.post("https://fp-it.portal101.cn/deviceprofile/v4", json=json_data)
            result.raise_for_status()
            return result.json()

    async def fetch_x_xhh_tokenid(self) -> str:
        data = await self.v4()
        device_id = data.get("detail", {}).get("deviceId")
        if not device_id:
            raise Exception("获取 x_xhh_tokenid 失败")
        return f"B{device_id}"


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


if __name__ == "__main__":
    signer = XiaoHeiHeSign(method_key="g")
    result = signer.sign("/bbs/app/link/tree")
    print(result)
