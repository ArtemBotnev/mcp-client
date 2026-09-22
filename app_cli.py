import argparse
import os

from cli_ru import create_russian_parser
from config import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_RESPONSES_API_URL,
    DEFAULT_TIMEOUT_SECONDS,
    OPENAI_MODEL_ENV,
    OPENAI_RESPONSES_API_URL_ENV,
    AppConfig,
    resolve_mcp_server,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = create_russian_parser(
        description="Подключается к MCP-серверу и запускает CLI-диалог с LLM-агентом.",
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
    parser.add_argument(
        "--llm-timeout",
        metavar="СЕКУНДЫ",
        type=float,
        default=DEFAULT_LLM_TIMEOUT_SECONDS,
        help=f"Таймаут запроса к LLM API в секундах. По умолчанию: {DEFAULT_LLM_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--model",
        metavar="МОДЕЛЬ",
        default=os.getenv(OPENAI_MODEL_ENV, DEFAULT_OPENAI_MODEL),
        help=f"Модель OpenAI Responses API. По умолчанию: {OPENAI_MODEL_ENV} или {DEFAULT_OPENAI_MODEL}",
    )
    parser.add_argument(
        "--openai-api-url",
        metavar="URL",
        default=os.getenv(OPENAI_RESPONSES_API_URL_ENV, DEFAULT_OPENAI_RESPONSES_API_URL),
        help=f"URL Responses API. По умолчанию: {OPENAI_RESPONSES_API_URL_ENV} или {DEFAULT_OPENAI_RESPONSES_API_URL}",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Только вывести список инструментов MCP-сервера и завершить работу.",
    )
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        mcp_server=resolve_mcp_server(args.url, args.config),
        mcp_timeout=args.timeout,
        llm_timeout=args.llm_timeout,
        model=args.model,
        api_url=args.openai_api_url,
        list_tools_only=args.list_tools,
    )
