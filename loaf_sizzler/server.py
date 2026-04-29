"""Flask-based MCP server for loaf-sizzler."""

from __future__ import annotations

from flask import Flask, jsonify, request

from loaf_sizzler.tools.accept_bid import accept_bid
from loaf_sizzler.tools.accept_verifier import accept_verifier
from loaf_sizzler.tools.approve_usdc import approve_usdc
from loaf_sizzler.tools.bid_verify import bid_verify
from loaf_sizzler.tools.bid_job import bid_job
from loaf_sizzler.tools.clear_inbox import clear_inbox
from loaf_sizzler.tools.get_balance import get_balance
from loaf_sizzler.tools.get_inbox import get_inbox
from loaf_sizzler.tools.get_job_status import get_job_status
from loaf_sizzler.tools.get_output import get_output
from loaf_sizzler.tools.get_reputation import get_reputation
from loaf_sizzler.tools.list_jobs import list_jobs
from loaf_sizzler.tools.list_review_jobs import list_review_jobs
from loaf_sizzler.tools.post_job import post_job
from loaf_sizzler.tools.receive_message import receive_message
from loaf_sizzler.tools.submit_verdict import submit_verdict
from loaf_sizzler.tools.submit_work import submit_work


class MCPServer:
    """Flask MCP server for the Loaf Sizzler runtime."""

    def __init__(self, axl_client, contract_client, storage, port: int = 7100):
        """Store injected clients, storage, and server port."""
        self.axl_client = axl_client
        self.contract_client = contract_client
        self.storage = storage
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
                        {"name": "list_jobs", "description": "List open jobs from contract state."},
                        {"name": "list_review_jobs", "description": "List jobs currently in review."},
                        {"name": "get_job_status", "description": "Get current status for a specific job."},
                        {"name": "post_job", "description": "Create a new posted job on-chain."},
                        {"name": "accept_bid", "description": "Accept a worker bid for a job."},
                        {"name": "accept_verifier", "description": "Accept a verifier for a job."},
                        {"name": "bid_job", "description": "Send a bid to the poster agent over AXL."},
                        {"name": "submit_work", "description": "Write output hash to the contract."},
                        {"name": "bid_verify", "description": "Send a verifier bid to the poster agent over AXL."},
                        {"name": "get_output", "description": "Return stored output for an assigned verifier caller."},
                        {"name": "submit_verdict", "description": "Submit a verification verdict for a job."},
                        {"name": "get_balance", "description": "Get wallet balances and locked funds."},
                        {"name": "approve_usdc", "description": "Approve USDC allowance for protocol usage."},
                        {"name": "get_reputation", "description": "Get reputation data for an AXL key."},
                        {"name": "get_inbox", "description": "Read locally stored AXL inbox messages."},
                        {"name": "clear_inbox", "description": "Clear locally stored AXL inbox messages."},
                        {"name": "receive_message", "description": "Inbound tool — receives messages from remote agents over AXL"},
                    ]
                }
            elif method == "tools/call":
                params = payload.get("params") or {}
                name = params.get("name")
                args = params.get("arguments") or {}

                if name == "list_jobs":
                    result = list_jobs(args, self.contract_client)
                elif name == "list_review_jobs":
                    result = list_review_jobs(args, self.contract_client)
                elif name == "get_job_status":
                    result = get_job_status(args, self.contract_client)
                elif name == "post_job":
                    result = post_job(args, self.contract_client)
                elif name == "accept_bid":
                    result = accept_bid(args, self.axl_client, self.contract_client)
                elif name == "accept_verifier":
                    result = accept_verifier(args, self.axl_client, self.contract_client)
                elif name == "bid_job":
                    result = bid_job(args, self.axl_client)
                elif name == "submit_work":
                    result = submit_work(args, self.storage, self.contract_client)
                elif name == "bid_verify":
                    result = bid_verify(args, self.axl_client)
                elif name == "get_output":
                    caller_id = request.headers.get("X-From-Peer-Id", "")
                    result = get_output(args, self.storage, self.contract_client, caller_id)
                elif name == "submit_verdict":
                    result = submit_verdict(args, self.axl_client, self.contract_client)
                elif name == "get_balance":
                    result = get_balance(args, self.contract_client)
                elif name == "approve_usdc":
                    result = approve_usdc(args, self.contract_client)
                elif name == "get_reputation":
                    result = get_reputation(args, self.contract_client)
                elif name == "get_inbox":
                    result = get_inbox(args, self.storage)
                elif name == "clear_inbox":
                    result = clear_inbox(args, self.storage)
                elif name == "receive_message":
                    result = receive_message(args, self.storage)
                else:
                    result = {"status": "not implemented"}
            else:
                result = {"status": "not implemented"}

            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
            return jsonify(response), 200

        return app

    def start(self) -> None:
        """Run the server on the configured port."""
        app = self.create_app()
        app.run(host="0.0.0.0", port=self.port)


def create_app(axl_client, contract_client, storage, port: int = 7100) -> Flask:
    """Create the MCP HTTP server application."""
    return MCPServer(
        axl_client=axl_client,
        contract_client=contract_client,
        storage=storage,
        port=port,
    ).create_app()


def run_server(axl_client, contract_client, storage, port: int = 7100) -> None:
    """Run the MCP HTTP server on port 7100."""
    MCPServer(
        axl_client=axl_client,
        contract_client=contract_client,
        storage=storage,
        port=port,
    ).run()
