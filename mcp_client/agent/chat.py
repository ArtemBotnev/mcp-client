import json
from typing import Any, Protocol

from mcp import Client

from mcp_client.agent.time_normalization import with_normalized_time_context
from mcp_client.errors import LlmApiError, format_error
from mcp_client.integrations.mcp_tools import ToolRegistry, format_tool_output, parse_tool_arguments
from mcp_client.integrations.openai import OpenAiResponsesClient, extract_function_calls, extract_output_text

MAX_TOOL_CALL_ROUNDS = 8


class AgentObserver(Protocol):
    def tool_started(self, tool_name: str, arguments: dict[str, Any]) -> None:
        pass

    def tool_finished(self, *, is_error: bool) -> None:
        pass

    def tool_failed(self, message: str) -> None:
        pass


def build_system_prompt() -> str:
    return (
        "Ты русскоязычный CLI-ассистент. Веди короткий, понятный диалог с пользователем. "
        "Если для ответа нужны актуальные или внешние данные, используй доступные MCP-инструменты. "
        "Если пользователь просит отчет или сводку за период человеческим языком, используй нормализованный "
        "контекст клиента с ISO-8601 датами from/to и не заменяй его приблизительными датами. "
        "Если задача требует нескольких действий, вызывай MCP-инструменты последовательно: сначала получи данные, "
        "затем обработай их, затем выполни финальное действие вроде сохранения. "
        "Передавай результат предыдущего инструмента в следующий инструмент, если он нужен для продолжения цепочки. "
        "Если для вызова инструмента не хватает параметров, задай уточняющий вопрос вместо выдумывания. "
        "После результата инструмента отвечай пользователю человеческим текстом, не пересказывай JSON без необходимости."
    )


class McpLlmAgent:
    def __init__(
        self,
        *,
        mcp_client: Client,
        llm_client: OpenAiResponsesClient,
        model: str,
        registry: ToolRegistry,
        mcp_timeout: float,
        observer: AgentObserver,
    ) -> None:
        self.mcp_client = mcp_client
        self.llm_client = llm_client
        self.model = model
        self.registry = registry
        self.mcp_timeout = mcp_timeout
        self.observer = observer
        self.previous_response_id: str | None = None

    def reset(self) -> None:
        self.previous_response_id = None

    async def answer(self, user_message: str) -> str:
        normalized_message = with_normalized_time_context(user_message)
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": build_system_prompt(),
            "input": [{"role": "user", "content": normalized_message}],
            "tools": self.registry.openai_tools,
            "tool_choice": "auto",
        }
        if self.previous_response_id:
            payload["previous_response_id"] = self.previous_response_id

        response_data = await self.llm_client.create_response(payload)

        tool_call_round = 0
        while True:
            response_id = response_data.get("id")
            if isinstance(response_id, str):
                self.previous_response_id = response_id

            function_calls = extract_function_calls(response_data)
            if not function_calls:
                return self._extract_final_answer(response_data)

            tool_call_round += 1
            if tool_call_round > MAX_TOOL_CALL_ROUNDS:
                raise LlmApiError(
                    f"LLM превысил лимит последовательных вызовов инструментов: {MAX_TOOL_CALL_ROUNDS}.",
                )

            tool_outputs = await self._run_tool_calls(function_calls)
            if not tool_outputs:
                raise LlmApiError("LLM запросил инструменты, но не вернул корректные tool calls.")

            response_data = await self.llm_client.create_response(
                {
                    "model": self.model,
                    "instructions": build_system_prompt(),
                    "input": tool_outputs,
                    "tools": self.registry.openai_tools,
                    "tool_choice": "auto",
                    "previous_response_id": self.previous_response_id,
                },
            )

    def _extract_final_answer(self, response_data: dict[str, Any]) -> str:
        answer = extract_output_text(response_data)
        if answer:
            return answer

        status = response_data.get("status")
        if isinstance(status, str) and status != "completed":
            raise LlmApiError(f"LLM API вернул незавершенный ответ: {status}")
        raise LlmApiError("В ответе LLM API не найден текст ответа.")

    async def _run_tool_calls(self, function_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tool_outputs = []

        for call in function_calls:
            function_name = call.get("name")
            call_id = call.get("call_id")
            if not isinstance(function_name, str) or not isinstance(call_id, str):
                continue

            output = await self._run_single_tool_call(function_name, call.get("arguments"))
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            )

        return tool_outputs

    async def _run_single_tool_call(self, function_name: str, raw_arguments: Any) -> str:
        arguments, parse_error = parse_tool_arguments(raw_arguments)
        tool = self.registry.tool_by_function_name.get(function_name)

        if tool is None:
            return json.dumps({"error": f"Неизвестный инструмент: {function_name}"}, ensure_ascii=False)
        if parse_error is not None:
            return json.dumps({"error": parse_error}, ensure_ascii=False)

        self.observer.tool_started(tool.name, arguments)
        try:
            result = await self.mcp_client.call_tool(
                tool.name,
                arguments=arguments,
                read_timeout_seconds=self.mcp_timeout,
            )
            self.observer.tool_finished(is_error=getattr(result, "is_error", False))
            return format_tool_output(result)
        except Exception as error:
            message = format_error(error)
            self.observer.tool_failed(message)
            return json.dumps({"error": message}, ensure_ascii=False)
