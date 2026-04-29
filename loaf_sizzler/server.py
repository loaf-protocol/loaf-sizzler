"""Flask-based MCP server for loaf-sizzler."""

from __future__ import annotations

from flask import Flask, jsonify, request

from loaf_sizzler.tools.accept_bid import accept_bid
from loaf_sizzler.tools.bid_job import bid_job
from loaf_sizzler.tools.get_output import get_output
from loaf_sizzler.tools.get_reputation import get_reputation
from loaf_sizzler.tools.list_jobs import list_jobs
from loaf_sizzler.tools.post_job import post_job
from loaf_sizzler.tools.submit_work import submit_work
from loaf_sizzler.tools.verify_output import verify_output


class MCPServer:
    """Flask MCP server for the Loaf Sizzler runtime."""

    def __init__(self, axl_client, contract_client, port: int = 7100):
        """Store the injected clients and server port."""
        self.axl_client = axl_client
        self.contract_client = contract_client
        self.port = port

    def create_app(self) -> Flask:
        """Create the Flask application and register the MCP route."""
        app = Flask(__name__)

        @app.post("/mcp")
        def mcp() -> tuple[object, int]:
            """Handle MCP JSON-RPC requests."""
            payload = request.get_json(silent=True) or {}
            method = payload.get("method")
            request_id = payload.get("id")

            if method == "tools/list":
                result = {
                    "tools": [
                        {"name": "post_job", "description": "Write a job to the contract."},
                        {"name": "list_jobs", "description": "Read open jobs from the contract."},
                        {"name": "bid_job", "description": "Send a bid to the poster agent over AXL."},
                        {"name": "accept_bid", "description": "Write assignment to the contract."},
                        {"name": "submit_work", "description": "Write output hash to the contract."},
                        {"name": "get_output", "description": "Return stored output for an assigned verifier caller."},
                        {"name": "verify_output", "description": "Send a verdict over AXL."},
                        {"name": "get_reputation", "description": "Read reputation from the contract."},
                    ]
                }
            elif method == "tools/call":
                params = payload.get("params") or {}
                name = params.get("name")
                args = params.get("arguments") or {}

                if name == "post_job":
                    result = post_job(args, self.axl_client, self.contract_client)
                elif name == "list_jobs":
                    result = list_jobs(args, self.axl_client, self.contract_client)
                elif name == "bid_job":
                    result = bid_job(args, self.axl_client, self.contract_client)
                elif name == "accept_bid":
                    result = accept_bid(args, self.axl_client, self.contract_client)
                elif name == "submit_work":
                    result = submit_work(args, self.axl_client, self.contract_client)
                elif name == "get_output":
                    caller_id = request.headers.get("X-From-Peer-Id")
                    result = get_output(args, self.axl_client, self.contract_client, caller_id=caller_id)
                elif name == "verify_output":
                    result = verify_output(args, self.axl_client, self.contract_client)
                elif name == "get_reputation":
                    result = get_reputation(args, self.axl_client, self.contract_client)
                else:
                    result = {"status": "not implemented"}
            else:
                result = {"status": "not implemented"}

            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
            return jsonify(response), 200

        return app

    def run(self) -> None:
        """Run the server on the configured port."""
        app = self.create_app()
        app.run(host="0.0.0.0", port=self.port)


def create_app(axl_client, contract_client, port: int = 7100) -> Flask:
    """Create the MCP HTTP server application."""
    return MCPServer(axl_client=axl_client, contract_client=contract_client, port=port).create_app()


def run_server(axl_client, contract_client, port: int = 7100) -> None:
    """Run the MCP HTTP server on port 7100."""
    MCPServer(axl_client=axl_client, contract_client=contract_client, port=port).run()
