"""Flask-based MCP server for loaf-sizzler."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version

from flask import Flask, jsonify, request

from loaf_sizzler.tools.accept_bid import accept_bid
from loaf_sizzler.tools.approve_usdc import approve_usdc
from loaf_sizzler.tools.assign_verifier import assign_verifier
from loaf_sizzler.tools.bid_verify import bid_verify
from loaf_sizzler.tools.bid_job import bid_job
from loaf_sizzler.tools.claim_expired import claim_expired
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
from loaf_sizzler.tools.register_profile import register_profile
from loaf_sizzler.tools.submit_verdict import submit_verdict
from loaf_sizzler.tools.submit_work import submit_work
from loaf_sizzler.tools.update_axl_key import update_axl_key
from loaf_sizzler.tools.verify_output import verify_output


LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
}


def _package_version() -> str:
    try:
        return version("loaf-sizzler")
    except PackageNotFoundError:
        return "0.0.0"


def _schema(properties: dict | None = None, required: list[str] | None = None) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
    }
    if properties:
        schema["properties"] = properties
    if required:
        schema["required"] = required
    return schema


def _tool(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": _schema(properties, required),
    }


JOB_ID = {"type": ["integer", "string"], "description": "Loaf job id."}
AXL_KEY = {"type": "string", "description": "AXL public key for the target agent."}
AMOUNT = {
    "type": ["integer", "number", "string"],
    "description": "USDC amount. Decimal values are converted to 6-decimal raw units; integer values are treated as raw units.",
}

TOOL_DEFINITIONS = [
    _tool(
        "post_job",
        "Post a new job to the escrow contract.",
        {
            "criteria": {"type": "string"},
            "worker_amount": AMOUNT,
            "verifier_fee_each": AMOUNT,
            "verifier_count": {"type": "integer"},
            "quorum_threshold": {"type": "integer"},
            "min_verifier_score": {"type": "integer"},
            "expires_at": {"type": ["integer", "string"]},
        },
        [
            "criteria",
            "worker_amount",
            "verifier_fee_each",
            "verifier_count",
            "quorum_threshold",
            "min_verifier_score",
            "expires_at",
        ],
    ),
    _tool(
        "bid_job",
        "Send a bid to the poster agent over AXL.",
        {
            "poster_axl_key": AXL_KEY,
            "job_id": JOB_ID,
            "proposed_amount": AMOUNT,
        },
        ["poster_axl_key", "job_id"],
    ),
    _tool(
        "accept_bid",
        "Accept a worker bid for a job.",
        {
            "job_id": JOB_ID,
            "worker_profile_id": {"type": ["integer", "string"]},
            "agreed_worker_amount": AMOUNT,
            "worker_axl_key": AXL_KEY,
        },
        ["job_id", "worker_profile_id", "agreed_worker_amount", "worker_axl_key"],
    ),
    _tool(
        "assign_verifier",
        "Assign a verifier for a job.",
        {
            "job_id": JOB_ID,
            "verifier_profile_id": {"type": ["integer", "string"]},
            "verifier_axl_key": AXL_KEY,
            "worker_axl_key": AXL_KEY,
        },
        ["job_id", "verifier_profile_id", "verifier_axl_key", "worker_axl_key"],
    ),
    _tool(
        "submit_work",
        "Write output hash to the contract.",
        {
            "job_id": JOB_ID,
            "output": {"type": "string"},
        },
        ["job_id", "output"],
    ),
    _tool(
        "submit_verdict",
        "Submit a verification verdict for a job.",
        {
            "poster_axl_key": AXL_KEY,
            "job_id": JOB_ID,
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
            "reason": {"type": "string"},
        },
        ["poster_axl_key", "job_id", "verdict"],
    ),
    _tool(
        "verify_output",
        "Submit a verifier's verdict via AXL.",
        {
            "poster_axl_key": AXL_KEY,
            "job_id": JOB_ID,
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
            "reason": {"type": "string"},
        },
        ["poster_axl_key", "job_id", "verdict"],
    ),
    _tool(
        "get_output",
        "Return stored output for an assigned verifier caller.",
        {
            "job_id": JOB_ID,
            "verifier_profile_id": {"type": ["integer", "string"]},
        },
        ["job_id", "verifier_profile_id"],
    ),
    _tool(
        "bid_verify",
        "Send a verifier bid to the poster agent over AXL.",
        {
            "poster_axl_key": AXL_KEY,
            "job_id": JOB_ID,
        },
        ["poster_axl_key", "job_id"],
    ),
    _tool(
        "get_inbox",
        "Read locally stored AXL inbox messages. Optionally filter by message type.",
        {
            "type": {
                "type": "string",
                "enum": ["bid", "acceptance", "verify_bid", "verifier_acceptance", "settlement"],
            },
        },
    ),
    _tool("clear_inbox", "Clear locally stored AXL inbox messages."),
    {
        "name": "receive_message",
        "description": "Inbound tool - receives messages from remote agents over AXL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["bid", "acceptance", "verify_bid", "verifier_acceptance", "settlement"],
                },
                "job_id": JOB_ID,
            },
            "required": ["type"],
            "additionalProperties": True,
        },
    },
    _tool(
        "list_jobs",
        "List jobs by state. Defaults to open jobs.",
        {
            "state": {
                "type": "string",
                "description": "Semantic job state name.",
                "enum": ["open", "active", "in_review", "review", "settled", "resolved", "expired", "cancelled", "all"],
            },
        },
    ),
    _tool("list_review_jobs", "List jobs currently in review. Alias for list_jobs with state=in_review."),
    _tool("get_job_status", "Get current status for a specific job.", {"job_id": JOB_ID}, ["job_id"]),
    _tool("get_reputation", "Get reputation data for a profile id.", {"profile_id": {"type": ["integer", "string"]}}, ["profile_id"]),
    _tool("get_balance", "Get wallet balances and locked funds."),
    _tool("approve_usdc", "Approve USDC spending for the escrow contract.", {"amount": AMOUNT}),
    _tool("register_profile", "Register profile if not already registered.", {"axlPublicKey": {"type": "string"}}),
    _tool("claim_expired", "Claim a job after expiry.", {"job_id": JOB_ID}, ["job_id"]),
    _tool("update_axl_key", "Update profile AXL key on-chain.", {"new_key": AXL_KEY}, ["new_key"]),
]
TOOL_NAMES = {tool["name"] for tool in TOOL_DEFINITIONS}


def _jsonrpc_result(request_id, result: dict):
    return jsonify({"jsonrpc": "2.0", "id": request_id, "result": result}), 200


def _jsonrpc_error(request_id, code: int, message: str, data: dict | None = None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return jsonify({"jsonrpc": "2.0", "id": request_id, "error": error}), 200


def _tool_result(result: object) -> dict:
    if isinstance(result, dict):
        structured = result
    else:
        structured = {"result": result}

    is_error = "error" in structured
    text = structured["error"] if is_error else json.dumps(structured, default=str)
    payload = {
        **structured,
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured,
    }
    if is_error:
        payload["isError"] = True
    return payload


def _tool_execution_error(message: str) -> dict:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


class MCPServer:
    """Flask MCP server for the Loaf Sizzler runtime."""

    def __init__(self, axl_client, contract_client, storage, port=7100):
        """Store injected clients, storage, and server port."""
        self.axl_client = axl_client
        self.contract_client = contract_client
        self.storage = storage
        self.port = port

    def create_app(self) -> Flask:
        """Create the Flask application and register the MCP route."""
        app = Flask(__name__)

        @app.get("/mcp")
        def mcp_get() -> tuple[object, int]:
            """Return 405 because this server does not open a server-initiated SSE stream."""
            return jsonify({"error": "SSE stream not supported by this endpoint"}), 405

        @app.post("/mcp")
        def mcp() -> tuple[object, int]:
            """Handle MCP JSON-RPC requests."""
            payload = request.get_json(silent=True) or {}
            method = payload.get("method")
            request_id = payload.get("id")
            app.logger.debug("MCP request method=%s id=%s", method, request_id)

            if not method:
                return _jsonrpc_error(request_id, -32600, "Invalid Request: missing method")

            if method == "initialize":
                params = payload.get("params") or {}
                requested_version = params.get("protocolVersion")
                protocol_version = requested_version if requested_version in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
                return _jsonrpc_result(
                    request_id,
                    {
                        "protocolVersion": protocol_version,
                        "capabilities": {
                            "tools": {
                                "listChanged": False,
                            },
                        },
                        "serverInfo": {
                            "name": "loaf-sizzler",
                            "title": "Loaf Sizzler",
                            "version": _package_version(),
                        },
                        "instructions": "Use the listed tools to interact with the Loaf marketplace runtime.",
                    },
                )

            if method == "notifications/initialized":
                if request_id is None:
                    return "", 202
                return _jsonrpc_result(request_id, {})

            if method == "ping":
                return _jsonrpc_result(request_id, {})

            if method == "tools/list":
                return _jsonrpc_result(request_id, {"tools": TOOL_DEFINITIONS})

            if method == "tools/call":
                params = payload.get("params") or {}
                name = params.get("name")
                args = params.get("arguments") or {}

                if not name:
                    return _jsonrpc_error(request_id, -32602, "Missing tool name")
                if name not in TOOL_NAMES:
                    return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")

                try:
                    result = self._call_tool(name, args)
                except KeyError as exc:
                    missing = str(exc).strip("'")
                    result = _tool_execution_error(f"Missing required argument: {missing}")
                except Exception as exc:
                    result = _tool_execution_error(str(exc))
                else:
                    result = _tool_result(result)

                return _jsonrpc_result(request_id, result)

            if request_id is None:
                return "", 202

            return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")

        return app

    def _call_tool(self, name: str, args: dict) -> dict:
        """Dispatch a validated MCP tool call to the existing tool implementation."""
        if name == "post_job":
            return post_job(args, self.contract_client)

        if name == "bid_job":
            return bid_job(args, self.axl_client, self.contract_client)

        if name == "accept_bid":
            return accept_bid(args, self.axl_client, self.contract_client)

        if name == "assign_verifier":
            return assign_verifier(args, self.axl_client, self.contract_client)

        if name == "submit_work":
            return submit_work(args, self.storage, self.contract_client)

        if name == "submit_verdict":
            return submit_verdict(args, self.axl_client, self.contract_client)

        if name == "verify_output":
            return verify_output(args, self.axl_client)

        if name == "get_output":
            caller_id = request.headers.get("X-From-Peer-Id", "")
            return get_output(args, self.contract_client, self.storage, caller_id)

        if name == "bid_verify":
            return bid_verify(args, self.axl_client)

        if name == "list_jobs":
            return list_jobs(args, self.contract_client)

        if name == "list_review_jobs":
            return list_review_jobs(args, self.contract_client)

        if name == "get_job_status":
            return get_job_status(args, self.contract_client)

        if name == "get_reputation":
            return get_reputation(args, self.contract_client)

        if name == "get_balance":
            return get_balance(args, self.contract_client)

        if name == "approve_usdc":
            return approve_usdc(args, self.contract_client)

        if name == "register_profile":
            return register_profile(args, self.contract_client)

        if name == "claim_expired":
            return claim_expired(args, self.contract_client)

        if name == "update_axl_key":
            return update_axl_key(args, self.contract_client)

        if name == "get_inbox":
            return get_inbox(args, self.storage)

        if name == "clear_inbox":
            return clear_inbox(args, self.storage)

        if name == "receive_message":
            return receive_message(args, self.storage)

        return {"error": f"Unknown tool: {name}"}

    def start(self) -> None:
        """Run the server on the configured port."""
        app = self.create_app()
        app.run(host="0.0.0.0", port=self.port, debug=False)


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
    ).start()
