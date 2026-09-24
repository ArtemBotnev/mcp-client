from mcp import Client

from mcp_client.agent.chat import McpLlmAgent
from mcp_client.cli.console import ConsoleAgentObserver, ConsoleChat, print_connection_status, print_tools
from mcp_client.config import AppConfig, OPENAI_API_KEY_ENV
from mcp_client.errors import ConfigurationError
from mcp_client.integrations.mcp_tools import ToolRegistry, list_available_tools
from mcp_client.integrations.openai import OpenAiResponsesClient


class McpClientApplication:
    def __init__(self, *, config: AppConfig, api_key: str | None) -> None:
        self.config = config
        self.api_key = api_key

    async def run(self) -> None:
        print("⏳ Подключение к MCP-серверу...")
        async with Client(
            self.config.mcp_server.server,
            read_timeout_seconds=self.config.mcp_timeout,
        ) as mcp_client:
            tools = await list_available_tools(mcp_client)

            if self.config.list_tools_only:
                print_tools(self.config.mcp_server.label, tools)
                return

            if not self.api_key:
                raise ConfigurationError(f"Перед запуском чата задайте переменную окружения {OPENAI_API_KEY_ENV}.")

            print_connection_status(self.config.mcp_server.label, len(tools))

            llm_client = OpenAiResponsesClient(
                api_url=self.config.api_url,
                api_key=self.api_key,
                timeout=self.config.llm_timeout,
            )
            agent = McpLlmAgent(
                mcp_client=mcp_client,
                llm_client=llm_client,
                model=self.config.model,
                registry=ToolRegistry.from_mcp_tools(tools),
                mcp_timeout=self.config.mcp_timeout,
                observer=ConsoleAgentObserver(),
            )
            await ConsoleChat(
                agent=agent,
                server_label=self.config.mcp_server.label,
                tools=tools,
            ).run()
