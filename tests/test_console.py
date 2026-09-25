import io
import unittest
from contextlib import redirect_stdout

from mcp_client.cli.console import print_connection_status
from mcp_client.integrations.mcp_tools import ServerToolSet


class ConsoleTests(unittest.TestCase):
    def test_connection_status_prints_connected_server_names(self) -> None:
        output = io.StringIO()
        server_tool_sets = [
            ServerToolSet(server_id="weather", server_label="weather: http://127.0.0.1:8081/mcp", tools=[]),
            ServerToolSet(server_id="trains", server_label="trains: http://127.0.0.1:8082/mcp", tools=[]),
        ]

        with redirect_stdout(output):
            print_connection_status(server_tool_sets)

        self.assertIn("🌐 Подключены: weather, trains", output.getvalue())


if __name__ == "__main__":
    unittest.main()
