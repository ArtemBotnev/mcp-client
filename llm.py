import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from errors import LlmApiError


class OpenAiResponsesClient:
    def __init__(self, *, api_url: str, api_key: str, timeout: float) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout

    async def create_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._post_json, payload)

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.api_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise LlmApiError("LLM API вернул HTTP-ошибку.", status_code=error.code, details=details) from error
        except URLError as error:
            raise LlmApiError(f"Не удалось подключиться к LLM API: {error.reason}") from error
        except TimeoutError as error:
            raise LlmApiError("Истекло время ожидания ответа от LLM API.") from error

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise LlmApiError("LLM API вернул некорректный JSON.", details=raw_body[:1000]) from error


def extract_output_text(response_data: dict[str, Any]) -> str:
    direct_output_text = response_data.get("output_text")
    if isinstance(direct_output_text, str) and direct_output_text.strip():
        return direct_output_text.strip()

    text_parts: list[str] = []
    for item in response_data.get("output", []):
        if not isinstance(item, dict):
            continue

        content = item.get("content")
        if not isinstance(content, list):
            continue

        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in {"output_text", "text"}:
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())

    return "\n".join(text_parts).strip()


def extract_function_calls(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    calls = []
    for item in response_data.get("output", []):
        if isinstance(item, dict) and item.get("type") == "function_call":
            calls.append(item)
    return calls
