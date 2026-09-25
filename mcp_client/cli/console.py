import sys
from typing import Any

from mcp_client.agent.chat import McpLlmAgent
from mcp_client.errors import LlmApiError
from mcp_client.integrations.mcp_tools import ServerToolSet, get_tool_input_schema, serialize_schema

EXIT_COMMANDS = {"/exit", "/quit", "exit", "quit"}


class ConsoleAgentObserver:
    def tool_started(self, tool_name: str, arguments: dict[str, Any]) -> None:
        print(f"🔧 Выбран инструмент: {tool_name}")

    def tool_finished(self, *, is_error: bool) -> None:
        pass

    def tool_failed(self, message: str) -> None:
        pass


class ConsoleChat:
    def __init__(self, *, agent: McpLlmAgent, server_tool_sets: list[ServerToolSet]) -> None:
        self.agent = agent
        self.server_tool_sets = server_tool_sets

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
                print_tools(self.server_tool_sets)
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


def print_connection_status(server_tool_sets: list[ServerToolSet]) -> None:
    tools_count = sum(len(server_tools.tools) for server_tools in server_tool_sets)
    server_names = ", ".join(server_tools.server_id for server_tools in server_tool_sets)
    print("✅ Соединение установлено")
    print(f"🔗 MCP-серверов: {len(server_tool_sets)}")
    print(f"🌐 Подключены: {server_names}")
    print(f"🧰 Доступных инструментов: {tools_count}")


def print_tools(server_tool_sets: list[ServerToolSet]) -> None:
    print_connection_status(server_tool_sets)

    if not any(server_tools.tools for server_tools in server_tool_sets):
        print("⚠️ Сервер не вернул ни одного инструмента.")
        return

    print("\n🤖 Инструменты MCP-серверов:")
    for server_tools in server_tool_sets:
        print()
        print(f"🔗 {server_tools.server_id}: {server_tools.server_label}")
        if not server_tools.tools:
            print("   ⚠️ Сервер не вернул ни одного инструмента.")
            continue

        for tool in server_tools.tools:
            print()
            print(f"🔧 {server_tools.server_id}.{tool.name}")
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
