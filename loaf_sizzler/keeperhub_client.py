"""KeeperHub REST client for loaf-sizzler."""

from __future__ import annotations

import os
import time

import requests


KEEPERHUB_API_KEY = os.getenv("KEEPERHUB_API_KEY")
KEEPERHUB_BASE_URL = "https://app.keeperhub.com/api"

KH_WF_LIST_JOBS = os.getenv("KH_WF_LIST_JOBS")
KH_WF_LIST_REVIEW_JOBS = os.getenv("KH_WF_LIST_REVIEW_JOBS")
KH_WF_GET_JOB = os.getenv("KH_WF_GET_JOB")
KH_WF_GET_OUTPUT_HASH = os.getenv("KH_WF_GET_OUTPUT_HASH")
KH_WF_GET_REPUTATION = os.getenv("KH_WF_GET_REPUTATION")
KH_WF_IS_ASSIGNED_VERIFIER = os.getenv("KH_WF_IS_ASSIGNED_VERIFIER")
KH_WF_POST_JOB = os.getenv("KH_WF_POST_JOB")
KH_WF_ACCEPT_BID = os.getenv("KH_WF_ACCEPT_BID")
KH_WF_ACCEPT_VERIFIER = os.getenv("KH_WF_ACCEPT_VERIFIER")
KH_WF_SUBMIT_WORK = os.getenv("KH_WF_SUBMIT_WORK")
KH_WF_SUBMIT_VERDICT = os.getenv("KH_WF_SUBMIT_VERDICT")
KH_WF_APPROVE_USDC = os.getenv("KH_WF_APPROVE_USDC")


class KeeperHubClient:
    """Client for contract interaction via KeeperHub workflows."""

    def __init__(self):
        self.base_url = KEEPERHUB_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {KEEPERHUB_API_KEY}" if KEEPERHUB_API_KEY else "",
            "Content-Type": "application/json",
        }
        self.workflow_ids = {
            "list_jobs": KH_WF_LIST_JOBS,
            "list_review_jobs": KH_WF_LIST_REVIEW_JOBS,
            "get_job": KH_WF_GET_JOB,
            "get_output_hash": KH_WF_GET_OUTPUT_HASH,
            "get_reputation": KH_WF_GET_REPUTATION,
            "is_assigned_verifier": KH_WF_IS_ASSIGNED_VERIFIER,
            "post_job": KH_WF_POST_JOB,
            "accept_bid": KH_WF_ACCEPT_BID,
            "accept_verifier": KH_WF_ACCEPT_VERIFIER,
            "submit_work": KH_WF_SUBMIT_WORK,
            "submit_verdict": KH_WF_SUBMIT_VERDICT,
            "approve_usdc": KH_WF_APPROVE_USDC,
        }

    def setup(self):
        """
        Called once at startup.
        Validate all workflow IDs are set.
        Log warning for any missing IDs.
        Do NOT raise — missing IDs just mean that tool won't work yet.
        """
        print("[keeperhub] checking workflow IDs...")
        for workflow_name, workflow_id in self.workflow_ids.items():
            if workflow_id:
                print(f"[keeperhub] ✅ {workflow_name}: {workflow_id}")
            else:
                print(f"[keeperhub] ⚠️  {workflow_name}: not configured")

    def setup_workflows(self):
        """Compatibility alias for startup validation."""
        self.setup()

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_body,
                timeout=30,
            )
            response.raise_for_status()
            if response.text.strip():
                return response.json()
            return {}
        except Exception as exc:
            raise RuntimeError(f"KeeperHub request failed for {method} {path}: {exc}") from exc

    def _extract_execution_id(self, response: dict) -> str:
        for key in ("execution_id", "executionId", "id"):
            value = response.get(key)
            if value:
                return str(value)
        data = response.get("data")
        if isinstance(data, dict):
            for key in ("execution_id", "executionId", "id"):
                value = data.get(key)
                if value:
                    return str(value)
        raise ValueError(f"Could not find execution_id in KeeperHub response: {response}")

    def _extract_result_payload(self, response: dict) -> dict:
        if isinstance(response.get("result"), dict):
            return response["result"]
        if isinstance(response.get("data"), dict):
            return response["data"]
        return response

    def execute(self, workflow_name: str, arguments: dict = {}) -> dict:
        """
        Execute a pre-created KeeperHub workflow.

        1. get workflow_id from self.workflow_ids[workflow_name]
        2. POST {base_url}/workflows/{workflow_id}/execute
           body: { "inputData": arguments }
        3. extract execution_id from response
        4. poll until complete or failed
        5. return full execution result

        Raise if workflow_id is None (not configured yet)
        """
        workflow_id = self.workflow_ids.get(workflow_name)
        if not workflow_id:
            raise RuntimeError(f"KeeperHub workflow '{workflow_name}' is not configured")

        try:
            initial_response = self._request(
                "POST",
                f"/workflows/{workflow_id}/execute",
                json_body={"inputData": arguments},
            )
            execution_id = self._extract_execution_id(initial_response)
            return self._poll(execution_id)
        except Exception as exc:
            print(f"[keeperhub] workflow failure: {workflow_name} args={arguments} error={exc}")
            return {"error": str(exc)}

    def _poll(self, execution_id: str) -> dict:
        """
        Poll GET {base_url}/executions/{execution_id}
        every 2 seconds until status is
        "completed" or "failed".
        Max 30 attempts (60 second timeout).
        Return full response on completion.
        Raise on timeout.
        """
        last_response: dict | None = None
        for _ in range(30):
            last_response = self._request("GET", f"/executions/{execution_id}")
            status = str(last_response.get("status", "")).lower()
            if status in {"completed", "failed"}:
                return last_response
            time.sleep(2)
        raise TimeoutError(f"KeeperHub execution {execution_id} timed out after 60 seconds")

    def _unwrap_output(self, response: dict):
        payload = self._extract_result_payload(response)
        for key in ("output", "result", "value", "data"):
            value = payload.get(key)
            if value is not None:
                return value
        return payload

    # READ METHODS

    def list_jobs(self) -> list | dict:
        """Execute list_jobs workflow. Return jobs array."""
        try:
            return self._unwrap_output(self.execute("list_jobs", {}))
        except Exception as exc:
            print(f"[keeperhub] list_jobs failed: {exc}")
            return {"error": str(exc)}

    def list_review_jobs(self) -> list | dict:
        """Execute list_review_jobs workflow. Return jobs array."""
        try:
            return self._unwrap_output(self.execute("list_review_jobs", {}))
        except Exception as exc:
            print(f"[keeperhub] list_review_jobs failed: {exc}")
            return {"error": str(exc)}

    def get_job(self, job_id: int) -> dict:
        """Execute get_job workflow with job_id. Return job dict."""
        try:
            result = self._unwrap_output(self.execute("get_job", {"job_id": job_id}))
            return result if isinstance(result, dict) else {"job": result}
        except Exception as exc:
            print(f"[keeperhub] get_job failed: job_id={job_id} error={exc}")
            return {"error": str(exc)}

    def get_output_hash(self, job_id: int) -> str:
        """Execute get_output_hash workflow. Return hash string."""
        try:
            result = self._unwrap_output(self.execute("get_output_hash", {"job_id": job_id}))
            if isinstance(result, dict) and "error" in result:
                return result
            return str(result)
        except Exception as exc:
            print(f"[keeperhub] get_output_hash failed: job_id={job_id} error={exc}")
            return {"error": str(exc)}

    def get_reputation(self, agent_address: str) -> dict:
        """Execute get_reputation workflow. Return reputation dict."""
        try:
            result = self._unwrap_output(self.execute("get_reputation", {"agent_address": agent_address}))
            return result if isinstance(result, dict) else {"reputation": result}
        except Exception as exc:
            print(f"[keeperhub] get_reputation failed: agent_address={agent_address} error={exc}")
            return {"error": str(exc)}

    def is_assigned_verifier(self, job_id: int, axl_key: str) -> bool:
        """Execute is_assigned_verifier workflow. Return bool."""
        try:
            result = self._unwrap_output(
                self.execute("is_assigned_verifier", {"job_id": job_id, "axl_key": axl_key})
            )
            if isinstance(result, bool):
                return result
            if isinstance(result, str):
                return result.strip().lower() in {"true", "1", "yes", "y"}
            return bool(result)
        except Exception as exc:
            print(f"[keeperhub] is_assigned_verifier failed: job_id={job_id} axl_key={axl_key} error={exc}")
            return False

    def get_balance(self, wallet_address: str) -> dict:
        """
        Execute list_jobs workflow — placeholder.
        TODO: needs separate web3/check-token-balance workflow
        Return { usdc: 0, weth: 0, locked_usdc: 0, wallet_address }
        """
        return {
            "usdc": 0,
            "weth": 0,
            "locked_usdc": 0,
            "wallet_address": wallet_address,
        }

    # WRITES

    def post_job(
        self,
        criteria: str,
        payment: int,
        verifier_count: int,
        reputation_tier: int,
        poster_axl_key: str,
    ) -> dict:
        """
        Execute post_job workflow.
        Return { job_id, tx_hash } from execution result.
        """
        try:
            result = self._unwrap_output(
                self.execute(
                    "post_job",
                    {
                        "criteria": criteria,
                        "payment": payment,
                        "verifier_count": verifier_count,
                        "reputation_tier": reputation_tier,
                        "poster_axl_key": poster_axl_key,
                    },
                )
            )
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            print(f"[keeperhub] post_job failed: criteria={criteria} payment={payment} error={exc}")
            return {"error": str(exc)}

    def accept_bid(self, job_id: int, worker_address: str, worker_axl_key: str) -> dict:
        """Execute accept_bid workflow. Return { tx_hash }."""
        try:
            result = self._unwrap_output(
                self.execute(
                    "accept_bid",
                    {
                        "job_id": job_id,
                        "worker_address": worker_address,
                        "worker_axl_key": worker_axl_key,
                    },
                )
            )
            return result if isinstance(result, dict) else {"tx_hash": result}
        except Exception as exc:
            print(f"[keeperhub] accept_bid failed: job_id={job_id} worker_address={worker_address} error={exc}")
            return {"error": str(exc)}

    def accept_verifier(self, job_id: int, verifier_address: str, verifier_axl_key: str) -> dict:
        """Execute accept_verifier workflow. Return { tx_hash }."""
        try:
            result = self._unwrap_output(
                self.execute(
                    "accept_verifier",
                    {
                        "job_id": job_id,
                        "verifier_address": verifier_address,
                        "verifier_axl_key": verifier_axl_key,
                    },
                )
            )
            return result if isinstance(result, dict) else {"tx_hash": result}
        except Exception as exc:
            print(f"[keeperhub] accept_verifier failed: job_id={job_id} verifier_address={verifier_address} error={exc}")
            return {"error": str(exc)}

    def submit_work(self, job_id: int, output_hash: str) -> dict:
        """Execute submit_work workflow. Return { tx_hash }."""
        try:
            result = self._unwrap_output(
                self.execute("submit_work", {"job_id": job_id, "output_hash": output_hash})
            )
            return result if isinstance(result, dict) else {"tx_hash": result}
        except Exception as exc:
            print(f"[keeperhub] submit_work failed: job_id={job_id} error={exc}")
            return {"error": str(exc)}

    def submit_verdict(self, job_id: int, passed: bool) -> dict:
        """Execute submit_verdict workflow. Return { tx_hash }."""
        try:
            result = self._unwrap_output(
                self.execute("submit_verdict", {"job_id": job_id, "passed": passed})
            )
            return result if isinstance(result, dict) else {"tx_hash": result}
        except Exception as exc:
            print(f"[keeperhub] submit_verdict failed: job_id={job_id} passed={passed} error={exc}")
            return {"error": str(exc)}

    def approve_usdc(self, spender: str, amount: int) -> dict:
        """
        Execute approve_usdc workflow on USDC contract.
        USDC Sepolia: 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238
        Return { tx_hash }
        """
        try:
            result = self._unwrap_output(
                self.execute("approve_usdc", {"spender": spender, "amount": amount})
            )
            return result if isinstance(result, dict) else {"tx_hash": result}
        except Exception as exc:
            print(f"[keeperhub] approve_usdc failed: spender={spender} amount={amount} error={exc}")
            return {"error": str(exc)}
