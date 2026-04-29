"""AXL messaging client for loaf-sizzler."""

import json
import os

import requests


AXL_NODE_URL = os.getenv("AXL_NODE_URL", "http://localhost:9002")


class AxlClient:
    """Client for sending P2P agent messages through a local AXL node."""

    def __init__(self, node_url: str = None):
        """Initialize client with the configured local AXL node URL."""
        self.node_url = node_url or os.getenv("AXL_NODE_URL", "http://localhost:9002")
        self.own_key = None

    def send(self, peer_id: str, message: dict) -> dict:
        """Send a message to a remote agent over AXL via local node routing."""
        try:
            url = f"{self.node_url}/mcp/{peer_id}/loaf-sizzler"
            body = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "receive_message",
                    "arguments": message,
                },
            }
            print(f"[axl] POST to: {url}")
            print(f"[axl] body: {json.dumps(body)}")
            response = requests.post(url, json=body)
            print(f"[axl] response status: {response.status_code}")
            print(f"[axl] response body: {response.text}")
            return response.json()
        except Exception as exc:
            return {"error": str(exc)}

    def send_bid(self, poster_axl_key: str, job_id: str, bidder_axl_key: str) -> dict:
        """Worker sends a bid message to a poster agent."""
        return self.send(
            poster_axl_key,
            {
                "type": "bid",
                "job_id": job_id,
                "bidder_axl_key": bidder_axl_key,
            },
        )

    def send_acceptance(self, worker_axl_key: str, job_id: str, poster_axl_key: str) -> dict:
        """Poster notifies a worker that their bid was accepted."""
        return self.send(
            worker_axl_key,
            {
                "type": "acceptance",
                "job_id": job_id,
                "poster_axl_key": poster_axl_key,
            },
        )

    def send_verify_bid(self, poster_axl_key: str, job_id: str, verifier_axl_key: str) -> dict:
        """Verifier sends a verification bid to a poster agent."""
        return self.send(
            poster_axl_key,
            {
                "type": "verify_bid",
                "job_id": job_id,
                "verifier_axl_key": verifier_axl_key,
            },
        )

    def send_verifier_acceptance(self, verifier_axl_key: str, job_id: str, worker_axl_key: str) -> dict:
        """Poster notifies a verifier they were accepted, including worker key."""
        return self.send(
            verifier_axl_key,
            {
                "type": "verifier_acceptance",
                "job_id": job_id,
                "worker_axl_key": worker_axl_key,
            },
        )

    def send_verdict(self, poster_axl_key: str, job_id: str, verdict: str, reason: str) -> dict:
        """Verifier sends settlement verdict details to the poster agent."""
        return self.send(
            poster_axl_key,
            {
                "type": "settlement",
                "job_id": job_id,
                "result": verdict,
                "reason": reason,
            },
        )

    def request_output(self, worker_axl_key: str, job_id: str) -> dict:
        """Request output from worker by calling the public get_output MCP tool."""
        try:
            response = requests.post(
                f"{self.node_url}/mcp/{worker_axl_key}/loaf-sizzler",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 1,
                    "params": {
                        "name": "get_output",
                        "arguments": {"job_id": job_id},
                    },
                },
                timeout=10,
            )
            return response.json()
        except Exception as exc:
            return {"error": str(exc)}

    def get_own_key(self) -> str:
        """Fetch own AXL public key from the local node identity endpoint."""
        if self.own_key:
            return self.own_key

        try:
            response = requests.get(f"{self.node_url}/topology", timeout=10)
            data = response.json()
            self.own_key = data["our_public_key"]
            return self.own_key
        except Exception:
            return None
