from contextlib import AsyncExitStack

from mcp import Client

from mcp_client.agent.chat import McpLlmAgent
from mcp_client.cli.console import ConsoleAgentObserver, ConsoleChat, print_connection_status, print_tools
from mcp_client.config import AppConfig, OPENAI_API_KEY_ENV
from mcp_client.errors import ConfigurationError, format_error
from mcp_client.integrations.mcp_tools import ServerToolSet, ToolRegistry, list_available_tools
from mcp_client.integrations.openai import OpenAiResponsesClient


class McpClientApplication:
    def __init__(self, *, config: AppConfig, api_key: str | None) -> None:
        self.config = config
        self.api_key = api_key

    async def run(self) -> None:
        print("⏳ Подключение к MCP-серверам...")
        async with AsyncExitStack() as stack:
            server_tool_sets = []
            for server_config in self.config.mcp_servers:
                try:
                    mcp_client = await stack.enter_async_context(
                        Client(
                            server_config.server,
                            read_timeout_seconds=self.config.mcp_timeout,
                        ),
                    )
                    tools = await list_available_tools(mcp_client)
                except Exception as error:
                    message = (
                        f"Не удалось подключиться к MCP-серверу {server_config.id}: "
                        f"{format_error(error)}"
                    )
                    if server_config.required:
                        raise ConfigurationError(message) from error
                    print(f"⚠️ {message}")
                    continue

                server_tool_sets.append(
                    ServerToolSet(
                        server_id=server_config.id,
                        server_label=server_config.label,
                        tools=tools,
                        client=mcp_client,
                    ),
                )

            if not server_tool_sets:
                raise ConfigurationError("Не удалось подключиться ни к одному MCP-серверу.")

            if self.config.list_tools_only:
                print_tools(server_tool_sets)
                return

            if not self.api_key:
                raise ConfigurationError(f"Перед запуском чата задайте переменную окружения {OPENAI_API_KEY_ENV}.")

            print_connection_status(server_tool_sets)

            llm_client = OpenAiResponsesClient(
                api_url=self.config.api_url,
                api_key=self.api_key,
                timeout=self.config.llm_timeout,
            )
            agent = McpLlmAgent(
                llm_client=llm_client,
                model=self.config.model,
                registry=ToolRegistry.from_mcp_server_tools(server_tool_sets),
                mcp_timeout=self.config.mcp_timeout,
                observer=ConsoleAgentObserver(),
                max_tool_call_rounds=self.config.max_tool_call_rounds if self.config.pipeline_enabled else 1,
            )
            await ConsoleChat(
                agent=agent,
                server_tool_sets=server_tool_sets,
            ).run()
