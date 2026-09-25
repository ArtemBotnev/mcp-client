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
MCP_SERVERS_KEY = "mcp.servers"
MCP_SERVER_BASE_URL_SUFFIX = "baseUrl"
MCP_SERVER_URL_SUFFIX = "url"
MCP_SERVER_REQUIRED_SUFFIX = "required"
MCP_SERVER_TRANSPORT_SUFFIX = "transport"
MCP_SERVER_STDIO_COMMAND_SUFFIX = "stdio.command"
MCP_SERVER_STDIO_ARGS_SUFFIX = "stdio.args"
MCP_SERVER_STDIO_CWD_SUFFIX = "stdio.cwd"
AGENT_PIPELINE_ENABLED_KEY = "agent.pipeline.enabled"
AGENT_PIPELINE_MAX_ITERATIONS_KEY = "agent.pipeline.maxIterations"

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "local.properties"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_LLM_TIMEOUT_SECONDS = 60
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_RESPONSES_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_PIPELINE_ENABLED = True
DEFAULT_PIPELINE_MAX_ITERATIONS = 8

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_MODEL"
OPENAI_RESPONSES_API_URL_ENV = "OPENAI_RESPONSES_API_URL"


@dataclass(frozen=True)
class McpServerConfig:
    id: str
    server: str | StdioServerParameters
    label: str
    required: bool = True


@dataclass(frozen=True)
class AppConfig:
    mcp_servers: list[McpServerConfig]
    mcp_timeout: float
    llm_timeout: float
    model: str
    api_url: str
    list_tools_only: bool
    pipeline_enabled: bool
    max_tool_call_rounds: int


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
        return McpServerConfig(id="default", server=url, label=url)

    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return McpServerConfig(id="default", server=env_url, label=env_url)

    config_path = Path(config_file)
    properties = load_properties(config_path)
    transport = properties.get(MCP_TRANSPORT_KEY, "http").strip().lower()

    if transport == "http":
        resolved_url = resolve_mcp_url(url, config_file)
        return McpServerConfig(id="default", server=resolved_url, label=resolved_url)

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

    return McpServerConfig(id="default", server=server, label=label)


def resolve_mcp_servers(url: str | None, config_file: str) -> list[McpServerConfig]:
    if url or os.getenv("MCP_SERVER_URL"):
        return [resolve_mcp_server(url, config_file)]

    config_path = Path(config_file)
    properties = load_properties(config_path)
    raw_server_ids = properties.get(MCP_SERVERS_KEY)
    if not raw_server_ids:
        return [resolve_mcp_server(url, config_file)]

    servers = []
    for server_id in split_csv(raw_server_ids):
        servers.append(resolve_named_mcp_server(server_id, properties))

    if not servers:
        raise ValueError(f"В {MCP_SERVERS_KEY} не указан ни один MCP-сервер.")

    return servers


def resolve_named_mcp_server(server_id: str, properties: dict[str, str]) -> McpServerConfig:
    prefix = f"{MCP_SERVERS_KEY}.{server_id}."
    required = parse_bool(properties.get(f"{prefix}{MCP_SERVER_REQUIRED_SUFFIX}"), default=True)
    transport = properties.get(f"{prefix}{MCP_SERVER_TRANSPORT_SUFFIX}", "http").strip().lower()

    if transport == "http":
        url = properties.get(f"{prefix}{MCP_SERVER_BASE_URL_SUFFIX}") or properties.get(f"{prefix}{MCP_SERVER_URL_SUFFIX}")
        if not url:
            raise ValueError(
                f"Для MCP-сервера {server_id} укажите "
                f"{prefix}{MCP_SERVER_BASE_URL_SUFFIX}=... или {prefix}{MCP_SERVER_URL_SUFFIX}=...",
            )
        return McpServerConfig(id=server_id, server=url, label=f"{server_id}: {url}", required=required)

    if transport != "stdio":
        raise ValueError(
            f"Неподдерживаемый транспорт MCP для сервера {server_id}: {transport}. "
            "Используйте transport=http или transport=stdio.",
        )

    command = properties.get(f"{prefix}{MCP_SERVER_STDIO_COMMAND_SUFFIX}")
    if not command:
        raise ValueError(f"Для stdio MCP-сервера {server_id} укажите {prefix}{MCP_SERVER_STDIO_COMMAND_SUFFIX}=...")

    raw_args = properties.get(f"{prefix}{MCP_SERVER_STDIO_ARGS_SUFFIX}", "")
    cwd = properties.get(f"{prefix}{MCP_SERVER_STDIO_CWD_SUFFIX}")
    server = StdioServerParameters(
        command=command,
        args=shlex.split(raw_args),
        cwd=cwd or None,
    )
    label = f"{server_id}: {' '.join([command, *server.args])}"
    if cwd:
        label = f"{label} (рабочая директория: {cwd})"

    return McpServerConfig(id=server_id, server=server, label=label, required=required)


def resolve_pipeline_enabled(config_file: str) -> bool:
    properties = load_properties(Path(config_file))
    return parse_bool(properties.get(AGENT_PIPELINE_ENABLED_KEY), default=DEFAULT_PIPELINE_ENABLED)


def resolve_max_tool_call_rounds(config_file: str) -> int:
    properties = load_properties(Path(config_file))
    raw_value = properties.get(AGENT_PIPELINE_MAX_ITERATIONS_KEY)
    if raw_value is None:
        return DEFAULT_PIPELINE_MAX_ITERATIONS

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{AGENT_PIPELINE_MAX_ITERATIONS_KEY} должен быть целым числом.") from error

    if value < 1:
        raise ValueError(f"{AGENT_PIPELINE_MAX_ITERATIONS_KEY} должен быть больше 0.")

    return value


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(f"Некорректное boolean-значение: {value}")


def get_openai_api_key() -> str | None:
    return os.getenv(OPENAI_API_KEY_ENV)
