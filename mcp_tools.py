import json
import re
from dataclasses import dataclass
from typing import Any

from mcp import Client

TOOL_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_-]")


@dataclass(frozen=True)
class ToolRegistry:
    openai_tools: list[dict[str, Any]]
    tool_by_function_name: dict[str, Any]

    @classmethod
    def from_mcp_tools(cls, tools: list[Any]) -> "ToolRegistry":
        openai_tools = []
        tool_by_function_name = {}
        used_names: set[str] = set()

        for tool in tools:
            function_name = normalize_function_name(tool.name, used_names)
            description = tool.description or f"MCP tool {tool.name}"
            if function_name != tool.name:
                description = f"{description}\nOriginal MCP tool name: {tool.name}"

            openai_tools.append(
                {
                    "type": "function",
                    "name": function_name,
                    "description": description,
                    "parameters": schema_to_dict(get_tool_input_schema(tool)),
                    "strict": False,
                },
            )
            tool_by_function_name[function_name] = tool

        return cls(openai_tools=openai_tools, tool_by_function_name=tool_by_function_name)


async def list_available_tools(client: Client) -> list[Any]:
    tools = []
    cursor = None

    while True:
        tools_response = await client.list_tools(cursor=cursor)
        tools.extend(tools_response.tools)
        cursor = tools_response.next_cursor
        if cursor is None:
            break

    return tools


def get_tool_input_schema(tool: Any) -> Any:
    input_schema = getattr(tool, "inputSchema", None)
    if input_schema is None:
        input_schema = getattr(tool, "input_schema", None)
    return input_schema


def serialize_schema(schema: Any) -> str:
    if schema is None:
        return "{}"

    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True, exclude_none=True)

    return json.dumps(schema, ensure_ascii=False, indent=2)


def schema_to_dict(schema: Any) -> dict[str, Any]:
    if schema is None:
        return {"type": "object", "properties": {}}

    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True, exclude_none=True)

    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    if schema.get("type") != "object":
        return {"type": "object", "properties": {}, "description": json.dumps(schema, ensure_ascii=False)}

    return schema


def normalize_function_name(name: str, used_names: set[str]) -> str:
    normalized = TOOL_NAME_PATTERN.sub("_", name).strip("_")
    if not normalized:
        normalized = "mcp_tool"

    candidate = normalized[:64]
    suffix = 2
    while candidate in used_names:
        suffix_text = f"_{suffix}"
        candidate = f"{normalized[:64 - len(suffix_text)]}{suffix_text}"
        suffix += 1

    used_names.add(candidate)
    return candidate


def parse_tool_arguments(raw_arguments: Any) -> tuple[dict[str, Any], str | None]:
    if raw_arguments is None:
        return {}, None
    if isinstance(raw_arguments, dict):
        return raw_arguments, None
    if not isinstance(raw_arguments, str):
        return {}, f"Аргументы инструмента должны быть JSON-объектом, получено: {type(raw_arguments).__name__}"
    if not raw_arguments.strip():
        return {}, None

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        return {}, f"Не удалось разобрать JSON аргументов инструмента: {error}"

    if not isinstance(arguments, dict):
        return {}, "Аргументы инструмента должны быть JSON-объектом."

    return arguments, None


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json", by_alias=True, exclude_none=True)
        except TypeError:
            return value.model_dump(by_alias=True, exclude_none=True)
    return value


def format_tool_output(result: Any) -> str:
    return json.dumps(to_jsonable(result), ensure_ascii=False, indent=2)
