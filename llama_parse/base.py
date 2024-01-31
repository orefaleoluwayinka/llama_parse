import asyncio
import httpx
import mimetypes
import time
from enum import Enum
from typing import List, Optional

from llama_index.bridge.pydantic import Field
from llama_index.readers.base import BasePydanticReader
from llama_index.schema import Document


class ResultType(str, Enum):
    """The result type for the parser."""

    TXT = "text"
    MD = "markdown"


class LlamaParser(BasePydanticReader):
    """A smart-parser for files."""

    base_url: str = Field(
        default="https://cloud.llamaindex.com/api/parsing",
        description="The base URL of the Llama Parsing API.",
    )
    result_type: ResultType = Field(
        default=ResultType.TXT, description="The result type for the parser."
    )
    check_interval: int = Field(
        default=1,
        description="The interval in seconds to check if the parsing is done.",
    )
    max_timeout: int = Field(
        default=2000,
        description="The maximum timeout in seconds to wait for the parsing to finish.",
    )

    def load_data(self, file_path: str, extra_info: Optional[dict] = None) -> List[Document]:
        """Load data from the input path."""
        return asyncio.run(self.aload_data(file_path, extra_info))

    async def aload_data(self, file_path: str, extra_info: Optional[dict] = None) -> List[Document]:
        """Load data from the input path."""
        if not file_path.endswith(".pdf"):
            raise Exception("Currently, only PDF files are supported.")

        extra_info = extra_info or {}
        extra_info["file_path"] = file_path

        # load data, set the mime type
        with open(file_path, "rb") as f:
            mime_type = mimetypes.guess_type(file_path)[0]
            files = {"pdf": (f.name, f, mime_type)}

            # send the request, start job
            url = f"{self.base_url}/upload"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, files=files)
                if not response.ok:
                    raise Exception(f"Failed to parse the PDF file: {response.text}")

        # check the status of the job, return when done
        job_id = response.json()["id"]
        status_url = f"{self.base_url}/job/{job_id}"

        start = time.time()
        while True:
            await asyncio.sleep(self.check_interval)
            async with httpx.AsyncClient() as client:
                status = await client.get(status_url)
                if not response.ok:
                    raise Exception(f"Failed to parse the PDF file: {response.text}")
                status = response.json()['status']
                if status == "completed":
                    result_url = f"{self.base_url}/job/{job_id}/result/{self.result_type.value}"
                    result = await client.get(result_url)
                    if not result.ok:
                        raise Exception(f"Failed to parse the PDF file: {response.text}")
    
                    return [
                        Document(
                            text=result.json()[self.result_type.value],
                            metadata=extra_info,
                        )
                    ]
                elif status not in ("WAIT", "WAITING"):
                    raise Exception(f"Failed to parse the PDF file: {response.text}")

            if time.time() - start > self.max_timeout:
                raise Exception(
                    f"Timeout while parsing the PDF file: {response.text}"
                )