import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from mcp import StdioServerParameters

MCP_TRANSPORT_KEY = "mcp.transport"
MCP_SERVER_URL_KEY = "mcp.server.url"
MCP_STDIO_COMMAND_KEY = "mcp.stdio.command"
MCP_STDIO_ARGS_KEY = "mcp.stdio.args"
MCP_STDIO_CWD_KEY = "mcp.stdio.cwd"

DEFAULT_CONFIG_FILE = Path(__file__).with_name("local.properties")
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_LLM_TIMEOUT_SECONDS = 60
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_RESPONSES_API_URL = "https://api.openai.com/v1/responses"

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_MODEL"
OPENAI_RESPONSES_API_URL_ENV = "OPENAI_RESPONSES_API_URL"


@dataclass(frozen=True)
class McpServerConfig:
    server: str | StdioServerParameters
    label: str


@dataclass(frozen=True)
class AppConfig:
    mcp_server: McpServerConfig
    mcp_timeout: float
    llm_timeout: float
    model: str
    api_url: str
    list_tools_only: bool


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


def resolve_mcp_url(url: str | None, config_file: str) -> str:
    if url:
        return url

    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return env_url

    config_path = Path(config_file)
    properties = load_properties(config_path)
    config_url = properties.get(MCP_SERVER_URL_KEY)
    if config_url:
        return config_url

    raise ValueError(
        f"URL MCP-сервера не настроен. Добавьте {MCP_SERVER_URL_KEY}=... "
        f"в {config_path}, задайте MCP_SERVER_URL или передайте URL аргументом.",
    )


def resolve_mcp_server(url: str | None, config_file: str) -> McpServerConfig:
    if url:
        return McpServerConfig(server=url, label=url)

    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return McpServerConfig(server=env_url, label=env_url)

    config_path = Path(config_file)
    properties = load_properties(config_path)
    transport = properties.get(MCP_TRANSPORT_KEY, "http").strip().lower()

    if transport == "http":
        resolved_url = resolve_mcp_url(url, config_file)
        return McpServerConfig(server=resolved_url, label=resolved_url)

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

    return McpServerConfig(server=server, label=label)


def get_openai_api_key() -> str | None:
    return os.getenv(OPENAI_API_KEY_ENV)
