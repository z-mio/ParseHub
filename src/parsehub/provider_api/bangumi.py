from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from ..utils.helpers import UA

_TAG_RE = re.compile(
    r"\[(/?)(img|url|b|i|s|u|mask|quote|code|user|size|color|align|left|right|center|photo)(?:=([^\]]*))?\]",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"/(?:(subject/topic|group/topic)/(\d+)|blog/(\d+))(?:/|$)")
_API_BASE = "https://next.bgm.tv/p1"

# 数据来源：bangumi/frontend packages/utils/sticker-names.ts
_CHARACTER_STICKER_NAMES: dict[int, str] = {
    1: "Bits",
    2: "硬币",
    3: "喜欢",
    4: "点赞",
    5: "收藏",
    6: "叹号",
    7: "问号",
    8: "点头",
    9: "摇头",
    10: "紧张 1",
    11: "紧张 2",
    12: "惊吓",
    13: "汗",
    14: "生气",
    15: "庆祝",
    16: "自我安慰",
    17: "哭 1",
    18: "哭 2",
    19: "哭 3",
    20: "死亡",
    21: "头晕",
    22: "呆 1",
    23: "呆 2",
    24: "呆 3",
    25: "呆(贴纸) 1",
    26: "呆(贴纸) 2",
    27: "呆(贴纸) 3",
    28: "催眠",
    29: "笑",
    30: "笑(指)",
    31: "害羞 1",
    32: "害羞 2",
    33: "睡觉(普通)",
    34: "睡觉(准备阶段1)",
    35: "睡觉(准备阶段2)",
    36: "睡觉 (UU)",
    37: "闲置",
    38: "闲置 2",
    39: "说话",
    40: "说话 2",
    41: "期待",
    42: "唱歌",
    43: "到达",
    44: "到达(拿筷子)",
    45: "到达(拿勺子)",
    46: "摇铃",
    47: "敲头",
    48: "蛋糕",
    49: "抓拍(手机)",
    50: "抓拍(摄像机)",
    51: "驾驶",
    52: "喝(饮料杯)",
    53: "馋(筷子)",
    54: "馋(刀叉)",
    55: "撬棍 1",
    56: "撬棍 2",
    57: "撬棍 3",
    58: "坐牢 1",
    59: "坐牢 2",
    60: "刀 1",
    61: "刀 2",
    62: "荧光棒 1",
    63: "荧光棒 2",
    64: "冒泡 1",
    65: "冒泡 2",
    66: "爱心 1",
    67: "爱心 2",
    68: "爱心 3",
    69: "静音 1",
    70: "静音 2",
    71: "记录 1",
    72: "记录 2",
    73: "红包 1",
    74: "红包 2",
    75: "玫瑰",
    76: "情书",
    77: "钱",
    78: "要米",
    79: "摸头",
    80: "说教",
    81: "指",
    82: "吃",
    83: "画板",
    84: "反向点赞",
    85: "点赞",
    86: "行",
    87: "打字(普通)",
    88: "打字(生气)",
    89: "打字(恼怒)",
    90: "工作(普通)",
    91: "工作(生气)",
    92: "工作(小睡)",
    93: "工作(疲倦)",
    94: "Raid 1",
    95: "Raid 2",
    96: "舔舔",
    97: "得分(0分)",
    98: "得分(10分)",
    99: "Bug",
    100: "加油",
    101: "复活节",
    102: "枪",
    103: "扩音器",
    104: "带薪拉屎(简单模式)",
    105: "带薪拉屎(困难模式)",
    106: "加载",
    107: "喷剂",
    108: "停止工作",
    109: "墨镜",
    110: "像素墨镜",
    111: "墨镜拿下来",
    112: "拍蝇",
    113: "胶带",
    114: "垃圾桶",
    115: "垃圾桶(闲置)",
    116: "垃圾桶(说话)",
    117: "垃圾桶(说教)",
    118: "主意",
}
_BLAKE_ONLY_IDS = {97, 98}


@dataclass
class _BBCodeNode:
    tag: str
    value: str | None = None
    children: list[str | _BBCodeNode] = field(default_factory=list)


@dataclass
class BangumiPost:
    title: str
    markdown_content: str
    images: list[str]


class Bangumi:
    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    async def parse(self, url: str) -> BangumiPost:
        match = _URL_RE.search(url)
        if not match:
            raise BangumiError("不支持的 Bangumi 链接")

        topic_type, topic_id, blog_id = match.groups()
        async with httpx.AsyncClient(proxy=self.proxy, timeout=30, headers={"User-Agent": UA}) as client:
            if blog_id:
                blog = await self._get_json(client, f"{_API_BASE}/blogs/{blog_id}")
                photos = await self._get_json(client, f"{_API_BASE}/blogs/{blog_id}/photos", params={"limit": 100})
                markdown_content, images = convert_bbcode(blog.get("content") or "")
                photo_urls = [
                    f"https://lain.bgm.tv/pic/photo/l/{photo['target'].lstrip('/')}"
                    for photo in photos.get("data", [])
                    if photo.get("target")
                ]
                content_images = set(images)
                extra_photo_urls = list(dict.fromkeys(url for url in photo_urls if url not in content_images))
                images = list(dict.fromkeys([*images, *photo_urls]))
                markdown_content += "".join(f"\n\n![]({url})" for url in extra_photo_urls)
                return BangumiPost(
                    title=blog.get("title") or "",
                    markdown_content=markdown_content,
                    images=images,
                )

            assert topic_type is not None and topic_id is not None
            api_type = "subjects" if topic_type == "subject/topic" else "groups"
            topic = await self._get_json(client, f"{_API_BASE}/{api_type}/-/topics/{topic_id}")
            replies = topic.get("replies") or []
            content = replies[0].get("content", "") if replies else ""
            markdown_content, images = convert_bbcode(content)
            return BangumiPost(
                title=topic.get("title") or "",
                markdown_content=markdown_content,
                images=images,
            )

    @staticmethod
    async def _get_json(client: httpx.AsyncClient, url: str, *, params: dict[str, int] | None = None) -> dict:
        response = await client.get(url, params=params)
        if not response.is_success:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            message = payload.get("message") if isinstance(payload, dict) else None
            raise BangumiError(str(message or f"HTTP {response.status_code}"))
        payload = response.json()
        if not isinstance(payload, dict):
            raise BangumiError(f"HTTP {response.status_code}: invalid JSON object")
        return payload


def _replace_character_sticker(match: re.Match[str]) -> str:
    sticker_type, sticker_code = match.groups()
    sticker_id = int(sticker_code)
    expected_code = f"{sticker_id:02d}" if sticker_id < 100 else str(sticker_id)
    if sticker_code != expected_code:
        return match.group(0)
    if sticker_id not in _CHARACTER_STICKER_NAMES or (sticker_type == "musume" and sticker_id in _BLAKE_ONLY_IDS):
        return match.group(0)
    return f"[{_CHARACTER_STICKER_NAMES[sticker_id]}]"


def convert_bbcode(content: str) -> tuple[str, list[str]]:
    content = content.replace("\r\n", "\n")
    content = re.sub(r"\((musume|blake)_(\d+)\)", _replace_character_sticker, content)

    root = _BBCodeNode("")
    stack = [root]
    position = 0
    for match in _TAG_RE.finditer(content):
        stack[-1].children.append(content[position : match.start()])
        closing, tag, value = match.groups()
        tag = tag.lower()
        if closing:
            for index in range(len(stack) - 1, 0, -1):
                if stack[index].tag == tag:
                    del stack[index:]
                    break
        else:
            node = _BBCodeNode(tag=tag, value=value)
            stack[-1].children.append(node)
            stack.append(node)
        position = match.end()
    stack[-1].children.append(content[position:])

    images: list[str] = []
    markdown_content = _render_nodes(root.children, images)
    return markdown_content.strip(), images


def _render_nodes(nodes: list[str | _BBCodeNode], images: list[str]) -> str:
    rendered: list[str] = []
    for node in nodes:
        if isinstance(node, str):
            rendered.append(node)
            continue

        body = _render_nodes(node.children, images)
        match node.tag:
            case "img":
                url = body.strip()
                if url:
                    images.append(url)
                    rendered.append(f"![]({url})")
            case "url" if node.value:
                rendered.append(f"[{body}]({node.value})")
            case "url":
                rendered.append(body)
            case "b":
                rendered.append(f"**{body}**")
            case "i":
                rendered.append(f"*{body}*")
            case "s":
                rendered.append(f"~~{body}~~")
            case "quote":
                quote = body.strip("\n")
                rendered.append("\n".join(f"> {line}" for line in quote.split("\n")) if quote else "")
            case "code":
                rendered.append(f"```\n{body.strip('\n')}\n```")
            case "user":
                rendered.append(f"@{body}")
            case _:
                rendered.append(body)
    return "".join(rendered)


class BangumiError(Exception):
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


__all__ = ["Bangumi", "BangumiError", "BangumiPost", "convert_bbcode"]
