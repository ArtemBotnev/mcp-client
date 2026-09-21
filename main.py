import argparse
import asyncio
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

from cli_ru import create_russian_parser
from mcp import Client, StdioServerParameters


MCP_TRANSPORT_KEY = "mcp.transport"
MCP_SERVER_URL_KEY = "mcp.server.url"
MCP_STDIO_COMMAND_KEY = "mcp.stdio.command"
MCP_STDIO_ARGS_KEY = "mcp.stdio.args"
MCP_STDIO_CWD_KEY = "mcp.stdio.cwd"
DEFAULT_CONFIG_FILE = Path(__file__).with_name("local.properties")
DEFAULT_TIMEOUT_SECONDS = 10


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = create_russian_parser(
        description="Подключается к MCP-серверу и выводит список доступных инструментов.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        metavar="URL",
        default=None,
        help="URL MCP-сервера. Имеет приоритет над MCP_SERVER_URL и local.properties.",
    )
    parser.add_argument(
        "--config",
        metavar="ФАЙЛ",
        default=os.getenv("MCP_CONFIG_FILE", str(DEFAULT_CONFIG_FILE)),
        help=f"Путь к properties-файлу. По умолчанию: {DEFAULT_CONFIG_FILE}",
    )
    parser.add_argument(
        "--timeout",
        metavar="СЕКУНДЫ",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Таймаут подключения в секундах. По умолчанию: {DEFAULT_TIMEOUT_SECONDS}",
    )
    return parser.parse_args(argv)


def load_properties(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    properties = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        if not separator:
            continue

        properties[key.strip()] = value.strip()

    return properties


def resolve_mcp_url(args: argparse.Namespace) -> str:
    if args.url:
        return args.url

    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return env_url

    config_path = Path(args.config)
    properties = load_properties(config_path)
    config_url = properties.get(MCP_SERVER_URL_KEY)
    if config_url:
        return config_url

    raise ValueError(
        f"URL MCP-сервера не настроен. Добавьте {MCP_SERVER_URL_KEY}=... "
        f"в {config_path}, задайте MCP_SERVER_URL или передайте URL аргументом.",
    )


def resolve_mcp_server(args: argparse.Namespace) -> tuple[str | StdioServerParameters, str]:
    if args.url:
        return args.url, args.url

    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return env_url, env_url

    config_path = Path(args.config)
    properties = load_properties(config_path)
    transport = properties.get(MCP_TRANSPORT_KEY, "http").strip().lower()

    if transport == "http":
        url = resolve_mcp_url(args)
        return url, url

    if transport != "stdio":
        raise ValueError(
            f"Неподдерживаемый транспорт MCP: {transport}. "
            "Используйте mcp.transport=http или mcp.transport=stdio.",
        )

    command = properties.get(MCP_STDIO_COMMAND_KEY)
    if not command:
        raise ValueError(f"Для stdio-транспорта укажите {MCP_STDIO_COMMAND_KEY}=...")

    raw_args = properties.get(MCP_STDIO_ARGS_KEY, "")
    cwd = properties.get(MCP_STDIO_CWD_KEY)
    server = StdioServerParameters(
        command=command,
        args=shlex.split(raw_args),
        cwd=cwd or None,
    )
    label = " ".join([command, *server.args])
    if cwd:
        label = f"{label} (рабочая директория: {cwd})"

    return server, label


def serialize_schema(schema: Any) -> str:
    if schema is None:
        return "{}"

    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True, exclude_none=True)

    return json.dumps(schema, ensure_ascii=False, indent=2)


def format_error(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        messages = [format_error(item) for item in error.exceptions]
        messages = [message for message in messages if message]
        return "; ".join(messages) or str(error)

    cause = error.__cause__ or error.__context__
    if cause is not None:
        cause_message = format_error(cause)
        if cause_message and cause_message != str(error):
            return f"{error}: {cause_message}"

    return str(error) or error.__class__.__name__


async def print_available_tools(server: str | StdioServerParameters, label: str, timeout: float) -> None:
    print("⏳ Подключение к MCP-серверу...")
    async with Client(server, read_timeout_seconds=timeout) as client:
        tools = []
        cursor = None

        while True:
            tools_response = await client.list_tools(cursor=cursor)
            tools.extend(tools_response.tools)
            cursor = tools_response.next_cursor
            if cursor is None:
                break

        print("✅ Соединение установлено")
        print(f"🔗 Сервер: {label}")
        print(f"🧰 Доступных инструментов: {len(tools)}")

        if not tools:
            print("⚠️ Сервер не вернул ни одного инструмента.")
            return

        print("\n🤖 Инструменты MCP-сервера:")
        for tool in tools:
            input_schema = getattr(tool, "inputSchema", None)
            if input_schema is None:
                input_schema = getattr(tool, "input_schema", None)

            print()
            print(f"🔧 {tool.name}")
            print(f"   📝 Описание: {tool.description or 'Без описания'}")
            print("   📦 Схема входных данных:")
            print(serialize_schema(input_schema))


def main() -> None:
    args = parse_args()
    label = "<не настроен>"
    try:
        server, label = resolve_mcp_server(args)
        asyncio.run(print_available_tools(server, label, args.timeout))
    except TimeoutError:
        print(
            f"Не удалось подключиться к MCP-серверу за {args.timeout} секунд: {label}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as error:
        print(f"Не удалось подключиться к MCP-серверу: {format_error(error)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
