import asyncio
import sys

from app import McpClientApplication
from app_cli import build_config, parse_args
from config import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_RESPONSES_API_URL,
    DEFAULT_TIMEOUT_SECONDS,
    OPENAI_API_KEY_ENV,
    AppConfig,
    McpServerConfig,
    get_openai_api_key,
)
from errors import ConfigurationError, format_error


def main() -> None:
    config = AppConfig(
        mcp_server=McpServerConfig(server="<не настроен>", label="<не настроен>"),
        mcp_timeout=DEFAULT_TIMEOUT_SECONDS,
        llm_timeout=DEFAULT_LLM_TIMEOUT_SECONDS,
        model=DEFAULT_OPENAI_MODEL,
        api_url=DEFAULT_OPENAI_RESPONSES_API_URL,
        list_tools_only=False,
    )

    try:
        args = parse_args()
        config = build_config(args)
        api_key = get_openai_api_key()
        if not config.list_tools_only and not api_key:
            raise ConfigurationError(f"Перед запуском чата задайте переменную окружения {OPENAI_API_KEY_ENV}.")
        asyncio.run(McpClientApplication(config=config, api_key=api_key).run())
    except TimeoutError:
        print(
            f"Не удалось подключиться к MCP-серверу за {config.mcp_timeout} секунд: {config.mcp_server.label}",
            file=sys.stderr,
        )
        sys.exit(1)
    except ConfigurationError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(f"Не удалось подключиться к MCP-серверу: {format_error(error)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
