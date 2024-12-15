import os

import httpx
from httpx._types import ProxiesTypes
from tenacity import retry, stop_after_attempt


class ImgHost:
    def __init__(self, proxies: ProxiesTypes = None):
        self.async_client = httpx.AsyncClient(proxies=proxies)

    @retry(stop=stop_after_attempt(5))
    async def catbox(self, filename_or_url: str):
        host_url = "https://catbox.moe/user/api.php"
        is_url = "http" in str(filename_or_url)
        if is_url:
            response = await self.async_client.get(filename_or_url)
            filename = filename_or_url.split("/")[-1]
            with open(filename, "wb") as f:
                f.write(response.content)
        else:
            filename = filename_or_url

        file = open(filename, "rb")
        try:
            data = {
                "reqtype": "fileupload",
                "userhash": "",
            }
            response = await self.async_client.post(
                host_url, data=data, files={"fileToUpload": file}
            )
        finally:
            file.close()
        if is_url:
            os.remove(filename)

        await self.async_client.aclose()
        return response.text

    @retry(stop=stop_after_attempt(5))
    async def litterbox(self, filename: str):
        host_url = "https://litterbox.catbox.moe/resources/internals/api.php"

        file = open(filename, "rb")
        try:
            data = {
                "reqtype": "fileupload",
                "time": "1h",
            }
            response = await self.async_client.post(
                host_url, data=data, files={"fileToUpload": file}
            )
        finally:
            file.close()

        await self.async_client.aclose()
        return response.text
