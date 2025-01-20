import asyncio
from dataclasses import dataclass

import httpx
import os


class Azure:
    def __init__(
        self,
        endpoint: str = None,
        subscription_key: str = None,
    ):
        self.endpoint = endpoint or os.getenv("AZURE_SPEECH_REGION")
        self.subscription_key = subscription_key or os.getenv("AZURE_SPEECH_KEY")
        if not self.endpoint or not self.subscription_key:
            raise ValueError(
                "Azure 端点或密钥未配置, 请在环境变量中配置 AZURE_SPEECH_REGION 和 AZURE_SPEECH_KEY"
            )

    async def speech_to_text(self, audio_file_path: str):
        """
        长度小于 2 小时且大小小于 200 MB
        :param audio_file_path:
        :return:
        """
        url = (
            self.endpoint
            + "/speechtotext/transcriptions:transcribe?api-version=2024-11-15"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Media-Type": "multipart/form-data",
        }
        async with httpx.AsyncClient() as client:
            file = open(audio_file_path, "rb")
            r = await client.post(
                url,
                headers=headers,
                files={"audio": file},
                timeout=120,
            )
            file.close()
            if r.status_code == 200:
                return AzureResult.parse(r.json())
            else:
                raise Exception(f"Error: {r.status_code} - {r.text}")


@dataclass
class AzureResult:
    text: str
    phrases: list["Phrase"]

    @classmethod
    def parse(cls, data: dict) -> "AzureResult":
        text = "\n".join([i["text"] for i in data["combinedPhrases"]])
        chucks = [Phrase.parse(phrase) for phrase in data["phrases"]]
        return cls(text, chucks)


@dataclass
class Phrase:
    begin: float
    end: float
    text: str

    @classmethod
    def parse(cls, data: dict) -> "Phrase":
        offset = data["offsetMilliseconds"]
        duration = data["durationMilliseconds"]
        begin = offset / 1000.0
        end = (offset + duration) / 1000.0
        text = data["text"]
        return cls(begin, end, text)


if __name__ == "__main__":
    azure = Azure()
    result = asyncio.run(azure.speech_to_text(""))
