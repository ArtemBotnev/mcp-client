import json
import unittest
from dataclasses import dataclass
from typing import Any

from mcp_client.agent.chat import McpLlmAgent
from mcp_client.integrations.mcp_tools import ServerToolSet, ToolRegistry


@dataclass(frozen=True)
class FakeTool:
    name: str
    description: str
    inputSchema: dict[str, Any]


class FakeMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        read_timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append((name, arguments or {}))
        return {"tool": name, "arguments": arguments or {}, "timeout": read_timeout_seconds}


class FakeObserver:
    def tool_started(self, tool_name: str, arguments: dict[str, Any]) -> None:
        pass

    def tool_finished(self, *, is_error: bool) -> None:
        pass

    def tool_failed(self, message: str) -> None:
        pass


class FakeLlmClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.payloads: list[dict[str, Any]] = []

    async def create_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        if not self.responses:
            raise AssertionError("Unexpected LLM request")
        return self.responses.pop(0)


def tool(name: str) -> FakeTool:
    return FakeTool(
        name=name,
        description=f"{name} description",
        inputSchema={"type": "object", "properties": {}},
    )


def function_call(response_id: str, call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": response_id,
        "output": [
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        ],
    }


class MultiServerToolTests(unittest.IsolatedAsyncioTestCase):
    def build_registry(self, weather_client: FakeMcpClient, trains_client: FakeMcpClient) -> ToolRegistry:
        return ToolRegistry.from_mcp_server_tools(
            [
                ServerToolSet(
                    server_id="weather",
                    server_label="weather server",
                    tools=[tool("get_forecast"), tool("search")],
                    client=weather_client,
                ),
                ServerToolSet(
                    server_id="trains",
                    server_label="trains server",
                    tools=[tool("search_routes"), tool("search")],
                    client=trains_client,
                ),
            ],
        )

    async def test_registers_tools_from_multiple_servers(self) -> None:
        registry = self.build_registry(FakeMcpClient(), FakeMcpClient())

        names = [item["name"] for item in registry.openai_tools]

        self.assertIn("weather_get_forecast", names)
        self.assertIn("trains_search_routes", names)
        self.assertEqual(4, len(names))
        self.assertIn("MCP server: weather", registry.openai_tools[0]["description"])

    async def test_tool_name_collision_is_resolved_with_server_prefix(self) -> None:
        registry = self.build_registry(FakeMcpClient(), FakeMcpClient())

        names = [item["name"] for item in registry.openai_tools]

        self.assertIn("weather_search", names)
        self.assertIn("trains_search", names)

    async def test_routes_tool_call_to_correct_server(self) -> None:
        weather_client = FakeMcpClient()
        trains_client = FakeMcpClient()
        registry = self.build_registry(weather_client, trains_client)
        agent = McpLlmAgent(
            llm_client=FakeLlmClient([]),
            model="test-model",
            registry=registry,
            mcp_timeout=3,
            observer=FakeObserver(),
        )

        output = await agent._run_single_tool_call("trains_search_routes", {"from": "Москва"})

        self.assertIn("search_routes", output)
        self.assertEqual([], weather_client.calls)
        self.assertEqual([("search_routes", {"from": "Москва"})], trains_client.calls)

    async def test_long_flow_preserves_tool_call_order_across_servers(self) -> None:
        weather_client = FakeMcpClient()
        trains_client = FakeMcpClient()
        registry = self.build_registry(weather_client, trains_client)
        llm_client = FakeLlmClient(
            [
                function_call("r1", "c1", "weather_get_forecast", {"city": "Москва"}),
                function_call("r2", "c2", "trains_search_routes", {"from": "Москва", "to": "Санкт-Петербург"}),
                function_call("r3", "c3", "trains_search", {"routeId": "42"}),
                {
                    "id": "r4",
                    "output_text": "Готово: погода проверена, поезд найден.",
                    "output": [],
                },
            ],
        )
        agent = McpLlmAgent(
            llm_client=llm_client,
            model="test-model",
            registry=registry,
            mcp_timeout=3,
            observer=FakeObserver(),
            max_tool_call_rounds=4,
        )

        answer = await agent.answer("Составь план поездки")

        self.assertEqual("Готово: погода проверена, поезд найден.", answer)
        self.assertEqual([("get_forecast", {"city": "Москва"})], weather_client.calls)
        self.assertEqual(
            [
                ("search_routes", {"from": "Москва", "to": "Санкт-Петербург"}),
                ("search", {"routeId": "42"}),
            ],
            trains_client.calls,
        )
        self.assertEqual(["r1", "r2", "r3"], [payload["previous_response_id"] for payload in llm_client.payloads[1:]])


if __name__ == "__main__":
    unittest.main()
