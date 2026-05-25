import unittest

from loaf_sizzler.server import create_app
from loaf_sizzler.storage.memory import MemoryStorage


class MCPLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        app = create_app(None, None, self.storage)
        self.client = app.test_client()

    def post_rpc(self, payload):
        return self.client.post("/mcp", json=payload)

    def test_initialize_returns_server_capabilities(self):
        response = self.post_rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["jsonrpc"], "2.0")
        self.assertEqual(body["id"], 1)
        self.assertEqual(body["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("tools", body["result"]["capabilities"])
        self.assertEqual(body["result"]["serverInfo"]["name"], "loaf-sizzler")

    def test_initialized_notification_is_accepted(self):
        response = self.post_rpc(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data, b"")

    def test_tools_list_includes_input_schemas(self):
        response = self.post_rpc(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )

        body = response.get_json()
        tools = body["result"]["tools"]
        self.assertTrue(tools)
        self.assertTrue(all("inputSchema" in tool for tool in tools))
        self.assertIn("post_job", {tool["name"] for tool in tools})

    def test_tools_call_returns_mcp_content_and_existing_raw_fields(self):
        self.storage.add_message({"type": "bid", "job_id": "1"})
        response = self.post_rpc(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_inbox",
                    "arguments": {},
                },
            }
        )

        body = response.get_json()
        result = body["result"]
        self.assertEqual(result["messages"], [{"type": "bid", "job_id": "1"}])
        self.assertEqual(result["structuredContent"]["messages"], [{"type": "bid", "job_id": "1"}])
        self.assertEqual(result["content"][0]["type"], "text")

    def test_unknown_tool_returns_protocol_error(self):
        response = self.post_rpc(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "missing_tool",
                    "arguments": {},
                },
            }
        )

        body = response.get_json()
        self.assertEqual(body["error"]["code"], -32602)
        self.assertIn("Unknown tool", body["error"]["message"])


if __name__ == "__main__":
    unittest.main()
