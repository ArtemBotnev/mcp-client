import tempfile
import unittest
from pathlib import Path

from mcp_client.config import resolve_max_tool_call_rounds, resolve_mcp_servers, resolve_pipeline_enabled


class ConfigTests(unittest.TestCase):
    def write_config(self, text: str) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "local.properties"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_resolves_named_http_servers(self) -> None:
        config_file = self.write_config(
            "\n".join(
                [
                    "mcp.servers=weather,trains",
                    "mcp.servers.weather.baseUrl=http://127.0.0.1:8081/mcp",
                    "mcp.servers.weather.required=true",
                    "mcp.servers.trains.baseUrl=http://127.0.0.1:8082/mcp",
                    "mcp.servers.trains.required=false",
                ],
            ),
        )

        servers = resolve_mcp_servers(None, config_file)

        self.assertEqual(["weather", "trains"], [server.id for server in servers])
        self.assertEqual("http://127.0.0.1:8081/mcp", servers[0].server)
        self.assertTrue(servers[0].required)
        self.assertFalse(servers[1].required)

    def test_resolves_pipeline_settings(self) -> None:
        config_file = self.write_config(
            "\n".join(
                [
                    "agent.pipeline.enabled=false",
                    "agent.pipeline.maxIterations=12",
                ],
            ),
        )

        self.assertFalse(resolve_pipeline_enabled(config_file))
        self.assertEqual(12, resolve_max_tool_call_rounds(config_file))


if __name__ == "__main__":
    unittest.main()
