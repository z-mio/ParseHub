import base64
import hashlib
import random
import re
import time
from random import choice, randint
from urllib.parse import quote, urlencode

import httpx
from gmssl import func, sm3

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
)

POST_DETAIL = "https://www.douyin.com/aweme/v1/web/aweme/detail/"


class XBogus:
    def __init__(self, user_agent: str = None) -> None:
        self.Array = [
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            10,
            11,
            12,
            13,
            14,
            15,
        ]
        self.character = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe="
        self.ua_key = b"\x00\x01\x0c"
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    def md5_str_to_array(self, md5_str):
        if isinstance(md5_str, str) and len(md5_str) > 32:
            return [ord(char) for char in md5_str]
        array = []
        idx = 0
        while idx < len(md5_str):
            array.append((self.Array[ord(md5_str[idx])] << 4) | self.Array[ord(md5_str[idx + 1])])
            idx += 2
        return array

    def md5_encrypt(self, url_path):
        return self.md5_str_to_array(self.md5(self.md5_str_to_array(self.md5(url_path))))

    def md5(self, input_data):
        if isinstance(input_data, str):
            array = self.md5_str_to_array(input_data)
        elif isinstance(input_data, list):
            array = input_data
        else:
            raise ValueError("Invalid input type")
        md5_hash = hashlib.md5()
        md5_hash.update(bytes(array))
        return md5_hash.hexdigest()

    def encoding_conversion(self, a, b, c, e, d, t, f, r, n, o, i, _, x, u, s, ll, v, h, p):
        y = [a]
        y.append(int(i))
        y.extend([b, _, c, x, e, u, d, s, t, ll, f, v, r, h, n, p, o])
        return bytes(y).decode("ISO-8859-1")

    def encoding_conversion2(self, a, b, c):
        return chr(a) + chr(b) + c

    def rc4_encrypt(self, key, data):
        S = list(range(256))
        j = 0
        encrypted_data = bytearray()
        for i in range(256):
            j = (j + S[i] + key[i % len(key)]) % 256
            S[i], S[j] = S[j], S[i]
        i = j = 0
        for byte in data:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            encrypted_data.append(byte ^ S[(S[i] + S[j]) % 256])
        return encrypted_data

    def calculation(self, a1, a2, a3):
        x1 = (a1 & 255) << 16
        x2 = (a2 & 255) << 8
        x3 = x1 | x2 | a3
        return (
            self.character[(x3 & 16515072) >> 18]
            + self.character[(x3 & 258048) >> 12]
            + self.character[(x3 & 4032) >> 6]
            + self.character[x3 & 63]
        )

    def getXBogus(self, url_path):
        array1 = self.md5_str_to_array(
            self.md5(
                base64.b64encode(self.rc4_encrypt(self.ua_key, self.user_agent.encode("ISO-8859-1"))).decode(
                    "ISO-8859-1"
                )
            )
        )
        array2 = self.md5_str_to_array(self.md5(self.md5_str_to_array("d41d8cd98f00b204e9800998ecf8427e")))
        url_path_array = self.md5_encrypt(url_path)
        timer = int(time.time())
        ct = 536919696
        new_array = [
            64,
            0.00390625,
            1,
            12,
            url_path_array[14],
            url_path_array[15],
            array2[14],
            array2[15],
            array1[14],
            array1[15],
            timer >> 24 & 255,
            timer >> 16 & 255,
            timer >> 8 & 255,
            timer & 255,
            ct >> 24 & 255,
            ct >> 16 & 255,
            ct >> 8 & 255,
            ct & 255,
        ]
        xor_result = new_array[0]
        for i in range(1, len(new_array)):
            b = new_array[i]
            if isinstance(b, float):
                b = int(b)
            xor_result ^= b
        new_array.append(xor_result)
        array3, array4 = [], []
        idx = 0
        while idx < len(new_array):
            array3.append(new_array[idx])
            try:
                array4.append(new_array[idx + 1])
            except IndexError:
                pass
            idx += 2
        merge_array = array3 + array4
        garbled_code = self.encoding_conversion2(
            2,
            255,
            self.rc4_encrypt(
                "ÿ".encode("ISO-8859-1"),
                self.encoding_conversion(*merge_array).encode("ISO-8859-1"),
            ).decode("ISO-8859-1"),
        )
        xb_ = ""
        idx = 0
        while idx < len(garbled_code):
            xb_ += self.calculation(
                ord(garbled_code[idx]),
                ord(garbled_code[idx + 1]),
                ord(garbled_code[idx + 2]),
            )
            idx += 3
        return f"{url_path}&X-Bogus={xb_}", xb_, self.user_agent


class ABogus:
    __filter = re.compile(r"%([0-9A-F]{2})")
    __arguments = [0, 1, 14]
    __ua_key = "\u0000\u0001\u000e"
    __end_string = "cus"
    __version = [1, 0, 1, 5]
    __browser = "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel"
    __reg = [
        1937774191,
        1226093241,
        388252375,
        3666478592,
        2842636476,
        372324522,
        3817729613,
        2969243214,
    ]
    __str = {
        "s0": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
        "s1": "Dkdpgh4ZKsQB80/Mfvw36XI1R25+WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
        "s2": "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
        "s3": "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe",
        "s4": "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe",
    }

    def __init__(self, platform: str = None):
        self.chunk = []
        self.size = 0
        self.reg = self.__reg[:]
        self.ua_code = [
            76,
            98,
            15,
            131,
            97,
            245,
            224,
            133,
            122,
            199,
            241,
            166,
            79,
            34,
            90,
            191,
            128,
            126,
            122,
            98,
            66,
            11,
            14,
            40,
            49,
            110,
            110,
            173,
            67,
            96,
            138,
            252,
        ]
        self.browser = self.generate_browser_info(platform) if platform else self.__browser
        self.browser_len = len(self.browser)
        self.browser_code = self.char_code_at(self.browser)

    @classmethod
    def list_1(cls, random_num=None, a=170, b=85, c=45):
        return cls.random_list(random_num, a, b, 1, 2, 5, c & a)

    @classmethod
    def list_2(cls, random_num=None, a=170, b=85):
        return cls.random_list(random_num, a, b, 1, 0, 0, 0)

    @classmethod
    def list_3(cls, random_num=None, a=170, b=85):
        return cls.random_list(random_num, a, b, 1, 0, 5, 0)

    @staticmethod
    def random_list(a=None, b=170, c=85, d=0, e=0, f=0, g=0):
        r = a or (random.random() * 10000)
        v = [r, int(r) & 255, int(r) >> 8]
        v.append(v[1] & b | d)
        v.append(v[1] & c | e)
        v.append(v[2] & b | f)
        v.append(v[2] & c | g)
        return v[-4:]

    @staticmethod
    def from_char_code(*args):
        return "".join(chr(code) for code in args)

    @classmethod
    def generate_string_1(cls, random_num_1=None, random_num_2=None, random_num_3=None):
        return (
            cls.from_char_code(*cls.list_1(random_num_1))
            + cls.from_char_code(*cls.list_2(random_num_2))
            + cls.from_char_code(*cls.list_3(random_num_3))
        )

    def generate_string_2(self, url_params: str, method="GET", start_time=0, end_time=0):
        a = self.generate_string_2_list(url_params, method, start_time, end_time)
        e = self.end_check_num(a)
        a.extend(self.browser_code)
        a.append(e)
        return self.rc4_encrypt(self.from_char_code(*a), "y")

    def generate_string_2_list(self, url_params: str, method="GET", start_time=0, end_time=0):
        start_time = start_time or int(time.time() * 1000)
        end_time = end_time or (start_time + randint(4, 8))
        params_array = self.generate_params_code(url_params)
        method_array = self.generate_method_code(method)
        return self.list_4(
            (end_time >> 24) & 255,
            params_array[21],
            self.ua_code[23],
            (end_time >> 16) & 255,
            params_array[22],
            self.ua_code[24],
            (end_time >> 8) & 255,
            (end_time >> 0) & 255,
            (start_time >> 24) & 255,
            (start_time >> 16) & 255,
            (start_time >> 8) & 255,
            (start_time >> 0) & 255,
            method_array[21],
            method_array[22],
            int(end_time / 256 / 256 / 256 / 256) >> 0,
            int(start_time / 256 / 256 / 256 / 256) >> 0,
            self.browser_len,
        )

    @staticmethod
    def reg_to_array(a):
        o = [0] * 32
        for i in range(8):
            c = a[i]
            o[4 * i + 3] = 255 & c
            c >>= 8
            o[4 * i + 2] = 255 & c
            c >>= 8
            o[4 * i + 1] = 255 & c
            c >>= 8
            o[4 * i] = 255 & c
        return o

    def compress(self, a):
        f = self.generate_f(a)
        i = self.reg[:]
        for o in range(64):
            c = (self.de(i[0], 12) + i[4] + self.de(self.pe(o), o)) & 0xFFFFFFFF
            c = self.de(c, 7)
            s = (c ^ self.de(i[0], 12)) & 0xFFFFFFFF
            u = (self.he(o, i[0], i[1], i[2]) + i[3] + s + f[o + 68]) & 0xFFFFFFFF
            b = (self.ve(o, i[4], i[5], i[6]) + i[7] + c + f[o]) & 0xFFFFFFFF
            i[3], i[2], i[1], i[0] = i[2], self.de(i[1], 9), i[0], u
            i[7], i[6], i[5], i[4] = (
                i[6],
                self.de(i[5], 19),
                i[4],
                (b ^ self.de(b, 9) ^ self.de(b, 17)) & 0xFFFFFFFF,
            )
        for idx in range(8):
            self.reg[idx] = (self.reg[idx] ^ i[idx]) & 0xFFFFFFFF

    @classmethod
    def generate_f(cls, e):
        r = [0] * 132
        for t in range(16):
            r[t] = (e[4 * t] << 24 | e[4 * t + 1] << 16 | e[4 * t + 2] << 8 | e[4 * t + 3]) & 0xFFFFFFFF
        for n in range(16, 68):
            a = r[n - 16] ^ r[n - 9] ^ cls.de(r[n - 3], 15)
            a = a ^ cls.de(a, 15) ^ cls.de(a, 23)
            r[n] = (a ^ cls.de(r[n - 13], 7) ^ r[n - 6]) & 0xFFFFFFFF
        for n in range(68, 132):
            r[n] = (r[n - 68] ^ r[n - 64]) & 0xFFFFFFFF
        return r

    @staticmethod
    def pad_array(arr, length=60):
        while len(arr) < length:
            arr.append(0)
        return arr

    def fill(self, length=60):
        size = 8 * self.size
        self.chunk.append(128)
        self.chunk = self.pad_array(self.chunk, length)
        for i in range(4):
            self.chunk.append((size >> 8 * (3 - i)) & 255)

    @staticmethod
    def list_4(a, b, c, d, e, f, g, h, i, j, k, m, n, o, p, q, r):
        return [
            44,
            a,
            0,
            0,
            0,
            0,
            24,
            b,
            n,
            0,
            c,
            d,
            0,
            0,
            0,
            1,
            0,
            239,
            e,
            o,
            f,
            g,
            0,
            0,
            0,
            0,
            h,
            0,
            0,
            14,
            i,
            j,
            0,
            k,
            m,
            3,
            p,
            1,
            q,
            1,
            r,
            0,
            0,
            0,
        ]

    @staticmethod
    def end_check_num(a):
        r = 0
        for i in a:
            r ^= i
        return r

    @classmethod
    def decode_string(cls, url_string):
        return cls.__filter.sub(cls.replace_func, url_string)

    @staticmethod
    def replace_func(match):
        return chr(int(match.group(1), 16))

    @staticmethod
    def de(e, r):
        r %= 32
        return ((e << r) & 0xFFFFFFFF) | (e >> (32 - r))

    @staticmethod
    def pe(e):
        return 2043430169 if 0 <= e < 16 else 2055708042

    @staticmethod
    def he(e, r, t, n):
        if 0 <= e < 16:
            return (r ^ t ^ n) & 0xFFFFFFFF
        elif 16 <= e < 64:
            return (r & t | r & n | t & n) & 0xFFFFFFFF
        raise ValueError

    @staticmethod
    def ve(e, r, t, n):
        if 0 <= e < 16:
            return (r ^ t ^ n) & 0xFFFFFFFF
        elif 16 <= e < 64:
            return (r & t | ~r & n) & 0xFFFFFFFF
        raise ValueError

    @staticmethod
    def convert_to_char_code(a):
        return [ord(i) for i in a]

    @staticmethod
    def split_array(arr, chunk_size=64):
        return [arr[i : i + chunk_size] for i in range(0, len(arr), chunk_size)]

    @staticmethod
    def char_code_at(s):
        return [ord(char) for char in s]

    def write(self, e):
        self.size = len(e)
        if isinstance(e, str):
            e = self.decode_string(e)
            e = self.char_code_at(e)
        if len(e) <= 64:
            self.chunk = e
        else:
            chunks = self.split_array(e, 64)
            for i in chunks[:-1]:
                self.compress(i)
            self.chunk = chunks[-1]

    def reset(self):
        self.chunk, self.size = [], 0
        self.reg = self.__reg[:]

    def sum(self, e, length=60):
        self.reset()
        self.write(e)
        self.fill(length)
        self.compress(self.chunk)
        return self.reg_to_array(self.reg)

    @classmethod
    def generate_result_unit(cls, n, s):
        r = ""
        for i, j in zip(range(18, -1, -6), (16515072, 258048, 4032, 63), strict=True):
            r += cls.__str[s][(n & j) >> i]
        return r

    @classmethod
    def generate_result(cls, s, e="s4"):
        r = []
        for i in range(0, len(s), 3):
            if i + 2 < len(s):
                n = (ord(s[i]) << 16) | (ord(s[i + 1]) << 8) | ord(s[i + 2])
            elif i + 1 < len(s):
                n = (ord(s[i]) << 16) | (ord(s[i + 1]) << 8)
            else:
                n = ord(s[i]) << 16
            for j, k in zip(range(18, -1, -6), (0xFC0000, 0x03F000, 0x0FC0, 0x3F), strict=True):
                if j == 6 and i + 1 >= len(s):
                    break
                if j == 0 and i + 2 >= len(s):
                    break
                r.append(cls.__str[e][(n & k) >> j])
        r.append("=" * ((4 - len(r) % 4) % 4))
        return "".join(r)

    @classmethod
    def generate_args_code(cls):
        a = []
        for j in range(24, -1, -8):
            a.append(cls.__arguments[0] >> j)
        a.extend(
            [
                cls.__arguments[1] / 256,
                cls.__arguments[1] % 256,
                cls.__arguments[1] >> 24,
                cls.__arguments[1] >> 16,
            ]
        )
        for j in range(24, -1, -8):
            a.append(cls.__arguments[2] >> j)
        return [int(i) & 255 for i in a]

    def generate_method_code(self, method="GET"):
        return self.sm3_to_array(self.sm3_to_array(method + self.__end_string))

    def generate_params_code(self, params):
        return self.sm3_to_array(self.sm3_to_array(params + self.__end_string))

    @classmethod
    def sm3_to_array(cls, data):
        if isinstance(data, str):
            b = data.encode("utf-8")
        else:
            b = bytes(data)
        h = sm3.sm3_hash(func.bytes_to_list(b))
        return [int(h[i : i + 2], 16) for i in range(0, len(h), 2)]

    @staticmethod
    def generate_browser_info(platform="Win32"):
        inner_width = randint(1280, 1920)
        inner_height = randint(720, 1080)
        outer_width = randint(inner_width, 1920)
        outer_height = randint(inner_height, 1080)
        return "|".join(
            str(i)
            for i in [
                inner_width,
                inner_height,
                outer_width,
                outer_height,
                0,
                choice((0, 30)),
                0,
                0,
                outer_width,
                outer_height,
                outer_width,
                outer_height,
                inner_width,
                inner_height,
                24,
                24,
                platform,
            ]
        )

    @staticmethod
    def rc4_encrypt(plaintext, key):
        s = list(range(256))
        j = 0
        for i in range(256):
            j = (j + s[i] + ord(key[i % len(key)])) % 256
            s[i], s[j] = s[j], s[i]
        i = j = 0
        cipher = []
        for k in range(len(plaintext)):
            i = (i + 1) % 256
            j = (j + s[i]) % 256
            s[i], s[j] = s[j], s[i]
            cipher.append(chr(s[(s[i] + s[j]) % 256] ^ ord(plaintext[k])))
        return "".join(cipher)

    def get_value(
        self,
        url_params,
        method="GET",
        start_time=0,
        end_time=0,
        random_num_1=None,
        random_num_2=None,
        random_num_3=None,
    ):
        string_1 = self.generate_string_1(random_num_1, random_num_2, random_num_3)
        string_2 = self.generate_string_2(
            urlencode(url_params) if isinstance(url_params, dict) else url_params,
            method,
            start_time,
            end_time,
        )
        return self.generate_result(string_1 + string_2, "s4")


class DouyinWebCrawler:
    def __init__(self, cookie: str, proxy: str | None = None, user_agent: str = None):
        self.cookie = cookie
        self.proxy = proxy
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    def _get_headers(self):
        return {
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "User-Agent": self.user_agent,
            "Referer": "https://www.douyin.com/",
        }

    async def get_aweme_id(self, url: str) -> str:
        async with httpx.AsyncClient(proxy=self.proxy, timeout=10) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            response_url = str(response.url)
            for pattern in [
                re.compile(r"video/([^/?]*)"),
                re.compile(r"[?&]vid=(\d+)"),
                re.compile(r"note/([^/?]*)"),
                re.compile(r"modal_id=([0-9]+)"),
            ]:
                match = pattern.search(response_url)
                if match:
                    return match.group(1)
            raise ValueError("未在响应的地址中找到 aweme_id")

    async def fetch_one_video(self, aweme_id: str) -> dict:
        async with httpx.AsyncClient(
            headers=self._get_headers(), proxy=self.proxy, timeout=10, cookies=self.cookie
        ) as client:
            params = {
                "device_platform": "webapp",
                "aid": "6383",
                "channel": "channel_pc_web",
                "pc_client_type": "1",
                "version_code": "290100",
                "version_name": "29.1.0",
                "cookie_enabled": "true",
                "screen_width": "1920",
                "screen_height": "1080",
                "browser_language": "zh-CN",
                "browser_platform": "Win32",
                "browser_name": "Chrome",
                "browser_version": "130.0.0.0",
                "browser_online": "true",
                "engine_name": "Blink",
                "engine_version": "130.0.0.0",
                "os_name": "Windows",
                "os_version": "10",
                "cpu_core_num": "12",
                "device_memory": "8",
                "platform": "PC",
                "downlink": "10",
                "effective_type": "4g",
                "aweme_id": aweme_id,
            }
            a_bogus = ABogus().get_value(params)
            endpoint = f"{POST_DETAIL}?{urlencode(params)}&a_bogus={quote(a_bogus, safe='')}"
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()

    async def parse(self, url: str) -> dict:
        aweme_id = await self.get_aweme_id(url)
        return await self.fetch_one_video(aweme_id)
