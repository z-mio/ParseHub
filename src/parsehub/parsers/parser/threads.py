import asyncio
import re
from typing import Optional

import httpx

from ...types import (
    Image,
    ImageParseResult,
    MultimediaParseResult,
    ParseError,
    Video,
    VideoParseResult,
)
from ..base.base import BaseParser


class ThreadsParser(BaseParser):
    __platform_id__ = "threads"
    __platform__ = "Threads"
    __supported_type__ = ["视频", "图文"]
    __match__ = r"^(http(s)?://)?(www\.)?threads\.(net|com)/(t/|@.*/post/).*"
    __redirect_keywords__ = []

    async def parse(self, url: str) -> VideoParseResult | ImageParseResult | MultimediaParseResult | None:
        url = await self.get_raw_url(url)
        
        post_code = self.get_post_code(url)
        if not post_code:
            raise ValueError("Threads帖子链接无效")
        
        post_data = await self._fetch_post_metadata(post_code)
        
        # 构建基础信息
        k = {
            "title": post_data["title"],
            "desc": post_data["description"],
            "raw_url": url
        }
        
        # 根据媒体类型返回不同结果
        if post_data["video"]:
            # 有视频内容
            videos = [Video(v["url"]) for v in post_data["video"]]
            if len(videos) == 1:
                return VideoParseResult(video=videos[0], **k)
            else:
                # 多个视频，使用 MultimediaParseResult
                media = videos
                if post_data["images"]:
                    media.extend([Image(img["url"]) for img in post_data["images"]])
                return MultimediaParseResult(media=media, **k)
        elif post_data["images"]:
            # 只有图片
            images = [img["url"] for img in post_data["images"]]
            if post_data["imageType"] == "single":
                # 单张图片（可能是头像）
                return ImageParseResult(photo=images, **k)
            else:
                # 多张图片或轮播
                return MultimediaParseResult(
                    media=[Image(url) for url in images],
                    **k
                )
        else:
            # 纯文本帖子，返回带描述的结果
            return ImageParseResult(photo=[], **k)

    async def _fetch_post_metadata(self, post_code: str) -> dict:
        """获取帖子元数据"""
        try:
            # 将 post_code 转换为 post_id
            post_id = self._decode_post_id(post_code)
            
            # 构建 GraphQL 请求
            variables = {
                "check_for_unavailable_replies": True,
                "first": 10,
                "postID": str(post_id),
                "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": True,
                "__relay_internal__pv__BarcelonaIsThreadContextHeaderEnabledrelayprovider": False,
                "__relay_internal__pv__BarcelonaIsThreadContextHeaderFollowButtonEnabledrelayprovider": False,
                "__relay_internal__pv__BarcelonaUseCometVideoPlaybackEnginerelayprovider": False,
                "__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider": False,
                "__relay_internal__pv__BarcelonaIsViewCountEnabledrelayprovider": False,
                "__relay_internal__pv__BarcelonaShouldShowFediverseM075Featuresrelayprovider": False,
            }
            
            form_data = {
                "variables": str(variables).replace("'", '"').replace("True", "true").replace("False", "false"),
                "doc_id": "7448594591874178",
                "lsd": "hgmSkqDnLNFckqa7t1vJdn",
            }
            
            headers = {
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "X-Fb-Lsd": "hgmSkqDnLNFckqa7t1vJdn",
                "X-Ig-App-Id": "238260118697367",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            async with httpx.AsyncClient(proxy=self.cfg.proxy, timeout=30) as client:
                response = await client.post(
                    "https://www.threads.com/api/graphql",
                    data=form_data,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            
            # 检查错误
            if "errors" in data and len(data["errors"]) > 0:
                error_msg = data["errors"][0].get("summary", "Unknown error")
                raise ParseError(f"无法获取帖子内容: {error_msg}")
            
            if "data" not in data or not data["data"]:
                raise ParseError("无法获取帖子内容: 数据为空")
            
            # 解析帖子数据
            return self._parse_post_data(data, post_code)
            
        except httpx.TimeoutException as e:
            raise ParseError("解析超时") from e
        except httpx.HTTPError as e:
            raise ParseError(f"网络请求失败: {str(e)}") from e
        except Exception as e:
            raise ParseError(f"无法获取帖子内容: {str(e)}") from e

    def _parse_post_data(self, data: dict, post_code: str) -> dict:
        """解析帖子数据"""
        try:
            thread_items = data["data"]["data"]["edges"][0]["node"]["thread_items"]
            
            # 找到匹配的帖子
            post_obj = None
            index = 0
            for i, item in enumerate(thread_items):
                if item["post"]["code"] == post_code:
                    post_obj = item
                    index = i
                    break
            
            if not post_obj:
                raise ParseError("未找到匹配的帖子")
            
            post = post_obj["post"]
            
            # 处理标题和描述
            caption = ""
            if index > 0:
                # 这是回复
                prev_username = thread_items[index - 1]["post"]["user"]["username"]
                caption = f"⤴️ 回覆給 @{prev_username}\n\n"
            
            if post.get("caption") and post["caption"].get("text"):
                caption += post["caption"]["text"]
            
            username = post["user"]["username"]
            title = f"@{username} on Threads"
            
            # 处理图片
            images = []
            videos = []
            image_type = "single"
            has_reel = False
            
            # 检查轮播媒体
            if post.get("carousel_media") and len(post["carousel_media"]) > 0:
                for item in post["carousel_media"]:
                    if item.get("video_versions") and len(item["video_versions"]) > 0:
                        videos.append({
                            "url": item["video_versions"][0]["url"],
                            "type": "instagram"
                        })
                    elif item.get("image_versions2") and item["image_versions2"].get("candidates"):
                        images.append({
                            "url": item["image_versions2"]["candidates"][0]["url"]
                        })
                image_type = "carousel"
            # 检查链接预览
            elif (post.get("text_post_app_info") and 
                  post["text_post_app_info"].get("link_preview_attachment") and
                  post["text_post_app_info"]["link_preview_attachment"].get("image_url")):
                link_preview = post["text_post_app_info"]["link_preview_attachment"]
                if link_preview.get("url") and "instagram.com/reel" in link_preview["url"]:
                    has_reel = True
                    # 提取 reel ID
                    reel_match = re.search(r"/reel/([^/]+)", link_preview["url"])
                    if reel_match:
                        reel_id = reel_match.group(1)
                        videos.append({
                            "url": f"https://d.ddinstagram.com/reel/{reel_id}/",
                            "type": "ddinstagram"
                        })
                else:
                    images.append({"url": link_preview["image_url"]})
                    image_type = "carousel"
            # 检查普通图片
            elif post.get("image_versions2") and post["image_versions2"].get("candidates"):
                if len(post["image_versions2"]["candidates"]) > 0:
                    images.append({
                        "url": post["image_versions2"]["candidates"][0]["url"]
                    })
                    image_type = "carousel"
                else:
                    # 使用用户头像作为后备
                    images.append({
                        "url": post["user"]["profile_pic_url"]
                    })
                    image_type = "single"
            else:
                # 使用用户头像作为后备
                if post.get("user") and post["user"].get("profile_pic_url"):
                    images.append({
                        "url": post["user"]["profile_pic_url"]
                    })
                    image_type = "single"
            
            # 检查视频
            if post.get("video_versions") and len(post["video_versions"]) > 0:
                videos.append({
                    "url": post["video_versions"][0]["url"]
                })
            
            # 处理引用帖子
            quoted_post = None
            if (post.get("text_post_app_info") and 
                post["text_post_app_info"].get("share_info") and
                post["text_post_app_info"]["share_info"].get("quoted_post")):
                quoted = post["text_post_app_info"]["share_info"]["quoted_post"]
                quoted_username = quoted["user"]["username"]
                quoted_caption = quoted.get("caption", {}).get("text", "")
                caption += f"\n\n↪ 引用 @{quoted_username}\n{quoted_caption}"
                quoted_post = {
                    "username": quoted_username,
                    "caption": quoted_caption,
                    "quoted": True
                }
            
            return {
                "description": caption,
                "title": title,
                "images": images,
                "post": post_code,
                "username": username,
                "imageType": image_type,
                "video": videos,
                "quotedPost": quoted_post,
            }
            
        except (KeyError, IndexError, TypeError) as e:
            raise ParseError(f"解析帖子数据失败: {str(e)}") from e

    @staticmethod
    def _decode_post_id(post_code: str) -> int:
        """将 post_code 转换为 post_id"""
        # 清理 post_code
        post_code = post_code.split("?")[0]
        post_code = post_code.replace(" ", "").replace("/", "")
        
        # Base64 字母表
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        
        post_id = 0
        for char in post_code:
            post_id = post_id * 64 + alphabet.index(char)
        
        return post_id

    @staticmethod
    def get_post_code(url: str) -> Optional[str]:
        """从 URL 中提取 post code"""
        url = url.rstrip("/")
        
        # 匹配 /t/{code} 格式
        match = re.search(r"/t/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        
        # 匹配 /@username/post/{code} 格式
        match = re.search(r"/@[^/]+/post/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        
        return None


__all__ = ["ThreadsParser"]
