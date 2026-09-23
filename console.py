import json
import sys
from typing import Any

from agent import McpLlmAgent
from errors import LlmApiError
from mcp_tools import get_tool_input_schema, serialize_schema

EXIT_COMMANDS = {"/exit", "/quit", "exit", "quit"}


class ConsoleAgentObserver:
    def tool_started(self, tool_name: str, arguments: dict[str, Any]) -> None:
        print(f"🔧 Использую инструмент: {tool_name}")
        print(f"   Аргументы: {json.dumps(arguments, ensure_ascii=False)}")

    def tool_finished(self, *, is_error: bool) -> None:
        if is_error:
            print("   Результат: инструмент вернул ошибку")
        else:
            print("   Результат: получен")

    def tool_failed(self, message: str) -> None:
        print(f"   Ошибка: {message}")


class ConsoleChat:
    def __init__(self, *, agent: McpLlmAgent, server_label: str, tools: list[Any]) -> None:
        self.agent = agent
        self.server_label = server_label
        self.tools = tools

    async def run(self) -> None:
        print("\n💬 Диалог с MCP-агентом")
        print("Команды: /tools — список инструментов, /reset — сброс контекста, /exit — выход.")

        while True:
            try:
                user_message = input("\nВы: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nДо свидания!")
                return

            if not user_message:
                continue

            lower_message = user_message.lower()
            if lower_message in EXIT_COMMANDS:
                print("До свидания!")
                return
            if lower_message == "/tools":
                print_tools(self.server_label, self.tools)
                continue
            if lower_message == "/reset":
                self.agent.reset()
                print("Контекст диалога сброшен.")
                continue

            try:
                answer = await self.agent.answer(user_message)
            except LlmApiError as error:
                print(f"Ошибка LLM: {format_llm_error(error)}", file=sys.stderr)
                continue

            print(f"Агент: {answer}")


def print_connection_status(label: str, tools_count: int) -> None:
    print("✅ Соединение установлено")
    # print(f"🔗 Сервер: {label}")
    print(f"🧰 Доступных инструментов: {tools_count}")


def print_tools(label: str, tools: list[Any]) -> None:
    print_connection_status(label, len(tools))

    if not tools:
        print("⚠️ Сервер не вернул ни одного инструмента.")
        return

    print("\n🤖 Инструменты MCP-сервера:")
    for tool in tools:
        print()
        print(f"🔧 {tool.name}")
        print(f"   📝 Описание: {tool.description or 'Без описания'}")
        print("   📦 Схема входных данных:")
        print(serialize_schema(get_tool_input_schema(tool)))


def format_llm_error(error: LlmApiError) -> str:
    message = str(error)
    if error.status_code is not None:
        message = f"{message} Код HTTP: {error.status_code}."
    if error.details:
        message = f"{message} Подробности: {error.details}"
    return message
