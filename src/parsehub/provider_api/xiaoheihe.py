import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

import httpx
from markdownify import MarkdownConverter

# TODO: 逆向 EP 和 DATA
V4_EP = (
    "CFcLOAE8E7Ew0J7yxtc9hPtklLIOym8yh1eU5jpB6D0M86gJERnbWbE7wPEWM95v8cWsxACqGq7iU"
    "OEnrD2ODeFIj5VZdvbD3zhhOgT4FB6QfskCkuCN+JP/+aLz0rg/B+c/9fd5513ESuZxFVqUmrwe/v"
    "jqZh5nS6Bsyt50VN8="
)
V4_DATA = (
    "7ccf4483919143daa17cca371b849651ab10c58aa97415e3fcc9b2f4c0bc776844997f4059"
    "512c213b3cc965e84693188b08f1ddb8924922598173e0cfa0bab40f242bcd20e11c728da7"
    "5a75d64b75d4070affa0d64831d0b32efde8c74ac4e6adeef18bbcbd1d21131746d131e30c"
    "8ba5939ea8247e79534f6688fed7545d5060b069e85c19d11c0277ee8015d2a989d84ce1bd"
    "01ed2754a365959496343de0152044cef7db82d0353a091f566253f2f8ca14a192c64b610f"
    "643309079d235d355438c84f566943df3df71c2cc979a68c6f36ce62861d6ddb64874d03f8"
    "b596b1380de9f84a60aff650ec59e4b2427ba7492f541354ee4dfe09b02c7296539978d281"
    "2269a7d37121ba96133b7e2b5fdba4922efc6f4bacd31855ca2604b86096ed5abfa6b87656"
    "8298f4bd75c1de979608714b5f0ec2bd852ec6974f929891cfff70392b0c42c7efd9f53e6b"
    "52541d08d654f85d92b29b553b3ea4de3c0ddf88ea77815871e476d5ba8b61dfbb427e3147"
    "62b58a306479eeeb7831864bb593c91af9c85004e891efe5d495b3d1cb4885996ffeda2d50"
    "7f747be1022544cf6ca1e4663bba30d7e7be129b23c5dd4ee1b56d2c48969eeee5b7b0e062"
    "8cfc0527c5e2880c43a61dd753c72b76a0ec1556cac7682f54f0582b50419dbfaa504a9363"
    "54dcb289d282dfa94ded53d926a4385cf437e35afed207c8ccf9eea2e2d493b645034a79ea"
    "115b5df365cc3c6b160d0de25d5d94efd576538386521cc617058831a39bd9009555fe8bc3"
    "419e1f4c9c51271d3996dd5616d0071d850a36799296abb9084a8a6b406f62341ebe581d50"
    "11029c18e88074a2cd7e9fb6be16b948da4d696c624412a8adb4651af89e43db779ed90114"
    "001c7ad552a6baf80447c751c39ce85ce713a661dd7b67be37aa749b46d8827b2187401e8c"
    "3e26a5993b654d3b7e6a6323a512a00f925f887d7ce231f20788d999c527b63160b6b1893a"
    "5891ab183760ca28c95232c164563857a98b963838d385b9638295ded7b69eeb7a43185463"
    "d2278bd59409f5badc24abffcf5cab137f93d89657992b72c340d1a87ddec55a828d33857d"
    "ae8b27fc0aad082e14cd8ef294938dddd095f11dd842f94aa055f3b0ba880cc87771f0d61d"
    "cdc419027c010afb23d668b337cf63ce8359f51623326a81e7513beebfd98d3531b8c701b4"
    "cc58b42937245244228fcefe0c74b491e765e98ec0f71814788c347b5340163aaa8aae7c97"
    "332acb3270583f0d77c15c3216696ad4951e24a19107fd5fe150fc275198fe4c9794f2785d"
    "a3b0b840ebfe75e823b997f0d2eda75f5debbeced24462f1b976e5fc9d643858143d1b0ee4"
    "6dc3936991f50b5d9d7040a5d9f1cb202fbbc06420cdee16fafc0a6929789088ce8e695332"
    "b0178a64761a352b15d87aa3a40529febc881d46a3ae80933e407fc2b28c5e0771dd426b02"
    "1cf177e2ef53c94a0cc5fcc83212843955af3e5f3bb8b24e9ed121669dadd689d54644b507"
    "1581b0e882d4513220cdf1fd5345b76d1fe1d824357bf3acd8a1c58d4bfb4fe3f39922f72e"
    "2eb9a74ee4b5f248bf7e279569597f45ef0e7fcbefa2619dcf367fe3638cc93fe90583a72e"
    "4190729c8c5ab6dd6fb6a37b43eaa90c2e25530ac9d9e923492037f1f14c0da73e4968391f"
    "c96fe10e2bfbefd620bbd6ea4e948cf04d6219e2c32ee6875cb0c2515b3a9ff993438412d3"
    "b1b71ba4c50ea98216b50778a1c909cbb7802acc8348aad6a9118a91a9be87f8610a1ab363"
    "ba06beb726e0a5ce56820e6baf9de2d87a10ce1d5cdd2d94c9e0bab0a3b7b8809d52dd3926"
    "873caf244ab322a0f2f4c4d9c119153d0b3105c8321dd30378b5345418c5a509fe731aef31"
    "7b156cdd606d71b291954181fc3efd71467d809b90d2b02a876ddbe7c758c3189ff6ecca21"
    "44b2a63ef949d7b8b643e3ca7a20c2e5c843e6e34f0260d3963982510a8c077dd7f47158de"
    "ee71befbab650ef1fad54a622bf4d1c297d9a39995fb1420bdba52d20a939b2da9ec3d8a13"
    "b156a597f9de8a683ad68a5725a3d2afbdfdbf9c024793558ba6bbd1f6d5f520988358f6d8"
    "02c0ea8580d4f93218d729cf3bbec52e6224175a0f37dd5bb4901ec5efaa6625c6b6c3b452"
    "752584d2e634fdee181ef7772857de3831725a6bbb6a22c29a4ddee5e8d1bf5c9aebc1b863"
    "5ee14584163dae9d4fb2c28be4220a23bb889d1965b870c32273b0166f3195b22cb85fc570"
    "fb3b13335c49792aaef7b675135a5ced82efe0c36713d7b40123254a7cb0099139bc6634c3"
    "c1af20595392a6436b192b8e6bb43038a33dff4d22f6f11497cbcb5662e11f2d1510a77b61"
    "0d1150b15a76b6c916767f1f7f0883db4a0f7b96e9d9b0884249f965212ec1cb54056ee26d"
    "a2a883f29acdfc7040d4e2e99c4ffd42a8bb1c7852cb5b4c758cdc295baaf973eebd6e720c"
    "bf0bd6b30ad4a7133929e4b1223c4a579dc1dde1f4fdc1fec5a83c0e3d5335f2dc79e57efc"
    "74f64b4d69d0151d4025ee5392fd844f783e2c614903e0b3685362f142fa091dce36382c1d"
    "dc3a6a63815fe062c59e86cad9d26bb54dbf93297ad4ae75039719eddf659c22f0922f08fe"
    "9a2241200f87bfe60f92d9983062d868d5eaced8df5b2851f86b9ee00055d386bf1276ad9b"
    "b27f2fa4b04ca6e773ff7348eb078e7b3b20ac5f878552133a652793f630304d28f1dc8ecb"
    "eedf571f743ffb494c9b34a47df86df8530af4243f0fedfea466c374ff920571a998ebb799"
    "6c9b0ec4ef5780bd519f19106ad1a5b16183bf62cbc0d7d7e4c297df6c0870fd07825d29c9"
    "b51ecdc227efeda8848eaca34a4c65ef35c0d5d3fa6e02f416cf25c84ef054206906e0950e"
    "24250b6e8cbea114c42de785f2ac69204ff675c7bd8f89bb1f683b9adb1c08d73cea3b5cfe"
    "420fa46a893b9b4ba5674c502bebc59d492942af6eef30a09eb9ff94ead00ebc2007702868"
    "63ec52c88a45ec7cbe5414485d28c64112aca5015f1976c2bd772cacb7baa5ae267035c7a1"
    "d9703289821b84ef386f6998777f72f44392f28daa1dc23d26445ed5ca382405ae8b2b47a0"
    "06d56a040b55c6796328ace7d8faa040d3009e5b627e12c30ec6c02bff8de7173b9f393320"
    "3e0fb8e06f812ee8ba5a673f3fa31c27e5309a3f7e0a8a55829c0f5c8c7433bbc4db4cfce9"
    "aea6f37058dd0bcaef20b54546466bdef7b5f69745d4d4ba59c61bc64fd4202f9ce95cc8e1"
    "a56273db05551b6de959c5e2d5f2ccc6d9893d99e48a1ff043889c5bdcb96512ccff7237bd"
    "95fd344d3dd46e8d19743a65cde0aeace9ec6563f4c5d2a1dd6e72a32b48dc9444246d6d9e"
    "a5a9a8d4216b9e0b41f1e54179c52c9f456dbe6c4e8872627b54d7ca6957a270bac31a98cb"
    "2bacf895f30ed6a508b9bdeb288ccfbf5166cec8535ab73c5fa90b41f4ba5d8a55a7cfb8d9"
    "783e00356ee534676215463f0aa1333b3388c13c8c0f176af6d7d2a01e2dd01cac2eb73574"
    "bd6c0930c412cf12bcb80708706cc94b2b9546621f64547b8543179a203d9d871dfc4d5cd4"
    "8334f42598f62e7c8199782bd605c75dd719c0db51ed801a47938746caf258966fc3132f6c"
    "77b0a97ba78ece0e150fee450a90433d2b8534d276b07e8d4586043de0ffe1af106f026d45"
    "41ad961aea6f69fa92344ed9a93f76f2a9f0f29110a4f0a7bda6a84a46d815c68784ab6685"
    "466059376f0f8866107623c49d59acf60a010c923a73177ea9f58e187bcec2d6feb94a5220"
    "56325e1651b5499fd28c17456a756e171840b7f8f1d6785e3e63d0bb5a690cc148f45ba0b0"
    "6b5e0c8da2c6711a6b5011fdfc57221767bce9925d149f357cfa8f108965f9f6037f9b3bc9"
    "46d90499ec8c40108216ed10eea155cb8d8e7bf76cc17efc1fda962101dc22114ca7b3b39c"
    "44c3345d0e1c525e4cbdc1f49dbb66ad1f5874bb91a577cf66428fa861624febfb03c369d1"
    "9d794544"
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


class XHHConverter(MarkdownConverter):
    def convert_img(self, el, text, parent_tags):
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("data-original", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        if "_inline" in parent_tags and el.parent.name not in self.options["keep_inline_images_in"]:
            return alt

        return f"![{alt}]({src}{title_part})"


if __name__ == "__main__":
    signer = XiaoHeiHeSign(method_key="g")
    result = signer.sign("/bbs/app/link/tree")
    print(result)
