"""Contract client via KeeperHub workflows."""

from __future__ import annotations

import os
import time

import requests


KEEPERHUB_API_KEY = os.getenv("KEEPERHUB_API_KEY")
KEEPERHUB_BASE_URL = "https://app.keeperhub.com/api"
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
NETWORK = "11155111"

KH_WF_REGISTER_PROFILE = os.getenv("KH_WF_REGISTER_PROFILE")
KH_WF_POST_JOB = os.getenv("KH_WF_POST_JOB")
KH_WF_ACCEPT_BID = os.getenv("KH_WF_ACCEPT_BID")
KH_WF_ASSIGN_VERIFIER = os.getenv("KH_WF_ASSIGN_VERIFIER")
KH_WF_SUBMIT_WORK = os.getenv("KH_WF_SUBMIT_WORK")
KH_WF_SUBMIT_VERDICT = os.getenv("KH_WF_SUBMIT_VERDICT")
KH_WF_APPROVE_USDC = os.getenv("KH_WF_APPROVE_USDC")
KH_WF_CLAIM_EXPIRED = os.getenv("KH_WF_CLAIM_EXPIRED")
KH_WF_UPDATE_AXL_KEY = os.getenv("KH_WF_UPDATE_AXL_KEY")
KH_WF_GET_JOB = os.getenv("KH_WF_GET_JOB")
KH_WF_GET_PROFILE = os.getenv("KH_WF_GET_PROFILE")
KH_WF_GET_JOBS_BY_STATE = os.getenv("KH_WF_GET_JOBS_BY_STATE")
KH_WF_GET_REPUTATION = os.getenv("KH_WF_GET_REPUTATION")


class ContractClient:
    def __init__(self, axl_client, storage):
        self.base_url = KEEPERHUB_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {KEEPERHUB_API_KEY}",
            "Content-Type": "application/json",
        }
        self.axl_client = axl_client
        self.storage = storage
        self._profile_id = None

        self.workflow_ids = {
            "register_profile": KH_WF_REGISTER_PROFILE,
            "post_job": KH_WF_POST_JOB,
            "accept_bid": KH_WF_ACCEPT_BID,
            "assign_verifier": KH_WF_ASSIGN_VERIFIER,
            "submit_work": KH_WF_SUBMIT_WORK,
            "submit_verdict": KH_WF_SUBMIT_VERDICT,
            "approve_usdc": KH_WF_APPROVE_USDC,
            "claim_expired": KH_WF_CLAIM_EXPIRED,
            "update_axl_key": KH_WF_UPDATE_AXL_KEY,
            "get_job": KH_WF_GET_JOB,
            "get_profile": KH_WF_GET_PROFILE,
            "get_jobs_by_state": KH_WF_GET_JOBS_BY_STATE,
            "get_reputation": KH_WF_GET_REPUTATION,
        }

    def setup(self):
        """
        Called once from cli.py.
        Log status of each workflow ID:
        ✅ configured / ⚠️ not configured
        """
        print("[keeperhub] checking workflow IDs...")
        for name, wf_id in self.workflow_ids.items():
            if wf_id:
                print(f"[keeperhub] ✅ {name}: {wf_id}")
            else:
                print(f"[keeperhub] ⚠️  {name}: not configured")

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
        raise RuntimeError(f"execution id not found in response: {response}")

    def _extract_payload(self, response: dict):
        if isinstance(response.get("result"), dict):
            result = response["result"]
            for key in ("output", "result", "data"):
                if key in result:
                    return result[key]
            return result
        if "output" in response:
            return response["output"]
        if "data" in response:
            return response["data"]
        return response

    def _execute(self, workflow_name: str, arguments: dict = {}) -> dict:
        """
        Execute a KeeperHub workflow and poll for result.

        1. get workflow_id from self.workflow_ids[workflow_name]
        2. raise if workflow_id is None
        3. POST {base_url}/workflows/{workflow_id}/execute
           body: { "inputData": arguments }
        4. extract execution_id from response
        5. poll _poll(execution_id) until complete
        6. return result
        """
        workflow_id = self.workflow_ids.get(workflow_name)
        if not workflow_id:
            raise RuntimeError(f"workflow '{workflow_name}' is not configured")

        response = requests.post(
            f"{self.base_url}/workflows/{workflow_id}/execute",
            headers=self.headers,
            json={"inputData": arguments},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json() if response.text.strip() else {}
        execution_id = self._extract_execution_id(body)
        return self._poll(execution_id)

    def _poll(self, execution_id: str) -> dict:
        """
        Poll GET {base_url}/executions/{execution_id}
        every 2 seconds until status is completed or failed.
        Max 30 attempts (60 second timeout).
        Raise on timeout or failure.
        """
        last_response = None
        for _ in range(30):
            response = requests.get(
                f"{self.base_url}/executions/{execution_id}",
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            last_response = response.json() if response.text.strip() else {}

            status = str(last_response.get("status", "")).lower()
            if status == "completed":
                return last_response
            if status == "failed":
                raise RuntimeError(f"execution failed: {last_response}")
            time.sleep(2)

        raise TimeoutError(f"execution {execution_id} timed out after 60 seconds")

    def _ensure_registered(self) -> int:
        """
        Check storage for cached profileId first.
        If not cached, check contract via get_profile_by_address.
        If not registered, register automatically.
        Cache profileId in storage and self._profile_id.
        """
        if self._profile_id:
            return self._profile_id

        stored = self.storage.get_agent_data("profile_id")
        if stored:
            self._profile_id = int(stored)
            return self._profile_id

        profile = self.get_profile_by_address()
        if profile.get("exists"):
            self._profile_id = int(profile.get("id"))
            self.storage.set_agent_data("profile_id", str(self._profile_id))
            return self._profile_id

        print("[loaf-sizzler] first time setup — registering agent profile...")
        self._profile_id = self._register()
        self.storage.set_agent_data("profile_id", str(self._profile_id))
        print(f"[loaf-sizzler] profile registered: id={self._profile_id}")
        return self._profile_id

    def _register(self) -> int:
        """
        Register agent profile onchain via KeeperHub.
        Gets own AXL key from axl_client.
        Returns profileId extracted from execution result.
        """
        axl_key = self.axl_client.get_own_key()
        result = self._execute("register_profile", {"axlPublicKey": axl_key})
        payload = self._extract_payload(result)
        if isinstance(payload, dict):
            for key in ("profileId", "profile_id", "id"):
                if key in payload and payload[key] is not None:
                    return int(payload[key])
        raise RuntimeError(f"profileId not found in register result: {result}")

    def get_profile_by_address(self, address: str = None) -> dict:
        """
        Get profile for address.
        If address is None use own wallet address.
        Returns profile dict with exists field.
        If not found returns { exists: False }
        """
        arguments = {}
        if address is not None:
            arguments["address"] = address
            arguments["wallet"] = address
        try:
            result = self._execute("get_profile", arguments)
            payload = self._extract_payload(result)
            if not payload:
                return {"exists": False}
            if isinstance(payload, dict):
                if payload.get("exists") is False:
                    return {"exists": False}
                profile_id = payload.get("id") or payload.get("profileId") or payload.get("profile_id")
                if profile_id is None:
                    return {"exists": False}
                payload["id"] = int(profile_id)
                payload["exists"] = True
                return payload
            return {"exists": False}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: get_profile args={arguments} error={exc}")
            return {"exists": False}

    def get_profile(self, profile_id: int) -> dict:
        """Get profile by profileId."""
        arguments = {"profileId": profile_id}
        try:
            result = self._execute("get_profile", arguments)
            payload = self._extract_payload(result)
            if isinstance(payload, dict):
                payload.setdefault("exists", True)
                return payload
            return {"profile": payload, "exists": payload is not None}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: get_profile args={arguments} error={exc}")
            return {"error": str(exc)}

    def get_job(self, job_id: int) -> dict:
        """Get job by jobId."""
        arguments = {"jobId": job_id}
        try:
            result = self._execute("get_job", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"job": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: get_job args={arguments} error={exc}")
            return {"error": str(exc)}

    def _get_job_ids_by_state(self, state: int) -> list[int] | dict:
        arguments = {"state": state}
        try:
            result = self._execute("get_jobs_by_state", arguments)
            payload = self._extract_payload(result)
            if isinstance(payload, dict):
                ids = payload.get("jobIds") or payload.get("ids") or payload.get("jobs") or []
            else:
                ids = payload or []
            return [int(job_id) for job_id in ids]
        except Exception as exc:
            print(f"[keeperhub] workflow failure: get_jobs_by_state args={arguments} error={exc}")
            return {"error": str(exc)}

    def list_jobs(self) -> list:
        """
        Get OPEN jobs.
        getJobIdsByState(0) → list of IDs
        getJob(id) for each
        Return list of job dicts with poster axl_key included
        """
        ids = self._get_job_ids_by_state(0)
        if isinstance(ids, dict):
            return []

        jobs = []
        for job_id in ids:
            job = self.get_job(job_id)
            if not isinstance(job, dict) or job.get("error"):
                continue

            poster_profile_id = (
                job.get("posterProfileId")
                or job.get("poster_profile_id")
                or job.get("posterId")
                or job.get("poster_id")
            )
            if poster_profile_id is not None and "poster_axl_key" not in job and "posterAxlKey" not in job:
                profile = self.get_profile(int(poster_profile_id))
                if isinstance(profile, dict) and not profile.get("error"):
                    axl_key = profile.get("axlPublicKey") or profile.get("axl_key") or profile.get("axlKey")
                    if axl_key:
                        job["poster_axl_key"] = axl_key

            jobs.append(job)
        return jobs

    def list_review_jobs(self) -> list:
        """
        Get IN_REVIEW jobs.
        getJobIdsByState(2) → list of IDs
        getJob(id) for each
        """
        ids = self._get_job_ids_by_state(2)
        if isinstance(ids, dict):
            return []

        jobs = []
        for job_id in ids:
            job = self.get_job(job_id)
            if isinstance(job, dict) and not job.get("error"):
                jobs.append(job)
        return jobs

    def get_verifier_ids(self, job_id: int) -> list:
        """Get assigned verifier profileIds for a job."""
        job = self.get_job(job_id)
        if not isinstance(job, dict) or job.get("error"):
            return []
        verifiers = (
            job.get("verifierProfileIds")
            or job.get("verifier_profile_ids")
            or job.get("assignedVerifiers")
            or []
        )
        return [int(v) for v in verifiers]

    def get_reputation(self, profile_id: int) -> dict:
        """
        Get reputation scores for a profile.
        Returns {
            workerScore, verifierScore, posterScore,
            workerJobs, verifierJobs, posterJobs
        }
        """
        arguments = {"profileId": profile_id}
        try:
            result = self._execute("get_reputation", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"reputation": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: get_reputation args={arguments} error={exc}")
            return {"error": str(exc)}

    def is_assigned_verifier(self, job_id: int, profile_id: int) -> bool:
        """Check if profileId is assigned verifier for jobId."""
        verifier_ids = self.get_verifier_ids(job_id)
        return int(profile_id) in verifier_ids

    def get_output_hash(self, job_id: int) -> bytes:
        """Get outputHash from job as bytes32."""
        job = self.get_job(job_id)
        if not isinstance(job, dict) or job.get("error"):
            return b""
        value = job.get("outputHash") or job.get("output_hash") or ""
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            raw = value[2:] if value.startswith("0x") else value
            try:
                return bytes.fromhex(raw)
            except ValueError:
                return b""
        return b""

    def register_profile(self, axl_key: str) -> dict:
        """Execute register_profile workflow."""
        arguments = {"axlPublicKey": axl_key}
        try:
            result = self._execute("register_profile", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"result": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: register_profile args={arguments} error={exc}")
            return {"error": str(exc)}

    def post_job(
        self,
        criteria: str,
        worker_amount: int,
        verifier_fee_each: int,
        verifier_count: int,
        quorum_threshold: int,
        min_verifier_score: int,
        expires_at: int,
    ) -> dict:
        """
        _ensure_registered() first.
        Execute post_job workflow.
        Return { job_id, tx_hash }
        NOTE: no USDC approval needed here
        USDC locked at accept_bid
        """
        try:
            self._ensure_registered()
            arguments = {
                "criteria": criteria,
                "workerAmount": worker_amount,
                "verifierFeeEach": verifier_fee_each,
                "verifierCount": verifier_count,
                "quorumThreshold": quorum_threshold,
                "minVerifierScore": min_verifier_score,
                "expiresAt": expires_at,
            }
            result = self._execute("post_job", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"result": payload}
        except Exception as exc:
            print(
                "[keeperhub] workflow failure: "
                f"post_job args={{'criteria': {criteria}, 'workerAmount': {worker_amount}}} error={exc}"
            )
            return {"error": str(exc)}

    def accept_bid(self, job_id: int, worker_profile_id: int, agreed_worker_amount: int) -> dict:
        """
        _ensure_registered() first.
        Execute approve_usdc first:
            amount = agreed_worker_amount + (verifierFeeEach * verifierCount)
        Then execute accept_bid workflow.
        Return { tx_hash }
        """
        try:
            self._ensure_registered()

            job = self.get_job(job_id)
            verifier_fee_each = int(job.get("verifierFeeEach") or job.get("verifier_fee_each") or 0)
            verifier_count = int(job.get("verifierCount") or job.get("verifier_count") or 0)
            total_amount = int(agreed_worker_amount) + (verifier_fee_each * verifier_count)

            approval = self.approve_usdc(total_amount)
            if isinstance(approval, dict) and approval.get("error"):
                return approval

            arguments = {
                "jobId": job_id,
                "workerProfileId": worker_profile_id,
                "agreedWorkerAmount": agreed_worker_amount,
            }
            result = self._execute("accept_bid", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(
                "[keeperhub] workflow failure: "
                f"accept_bid args={{'jobId': {job_id}, 'workerProfileId': {worker_profile_id}, "
                f"'agreedWorkerAmount': {agreed_worker_amount}}} error={exc}"
            )
            return {"error": str(exc)}

    def assign_verifier(self, job_id: int, verifier_profile_id: int) -> dict:
        """
        _ensure_registered() first.
        Execute assign_verifier workflow.
        Return { tx_hash }
        NOTE: renamed from accept_verifier
        """
        arguments = {"jobId": job_id, "verifierProfileId": verifier_profile_id}
        try:
            self._ensure_registered()
            result = self._execute("assign_verifier", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: assign_verifier args={arguments} error={exc}")
            return {"error": str(exc)}

    def submit_work(self, job_id: int, output_hash: bytes) -> dict:
        """
        _ensure_registered() first.
        Execute submit_work workflow.
        output_hash is bytes32.
        Return { tx_hash }
        """
        arguments = {
            "jobId": job_id,
            "outputHash": f"0x{output_hash.hex()}",
        }
        try:
            self._ensure_registered()
            result = self._execute("submit_work", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: submit_work args={arguments} error={exc}")
            return {"error": str(exc)}

    def submit_verdict(self, job_id: int, passed: bool) -> dict:
        """
        _ensure_registered() first.
        Execute submit_verdict workflow.
        Return { tx_hash }
        """
        arguments = {"jobId": job_id, "passed": passed}
        try:
            self._ensure_registered()
            result = self._execute("submit_verdict", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: submit_verdict args={arguments} error={exc}")
            return {"error": str(exc)}

    def approve_usdc(self, amount: int) -> dict:
        """
        Execute approve_usdc workflow.
        Approves CONTRACT_ADDRESS to spend amount.
        Called internally by accept_bid.
        """
        arguments = {
            "token": USDC_ADDRESS,
            "spender": CONTRACT_ADDRESS,
            "amount": amount,
            "network": NETWORK,
        }
        try:
            result = self._execute("approve_usdc", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: approve_usdc args={arguments} error={exc}")
            return {"error": str(exc)}

    def claim_expired(self, job_id: int) -> dict:
        """
        _ensure_registered() first.
        Execute claim_expired workflow.
        Return { tx_hash }
        """
        arguments = {"jobId": job_id}
        try:
            self._ensure_registered()
            result = self._execute("claim_expired", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: claim_expired args={arguments} error={exc}")
            return {"error": str(exc)}

    def update_axl_key(self, new_key: str) -> dict:
        """
        _ensure_registered() first.
        Execute update_axl_key workflow.
        Return { tx_hash }
        """
        arguments = {"axlPublicKey": new_key}
        try:
            self._ensure_registered()
            result = self._execute("update_axl_key", arguments)
            payload = self._extract_payload(result)
            return payload if isinstance(payload, dict) else {"tx_hash": payload}
        except Exception as exc:
            print(f"[keeperhub] workflow failure: update_axl_key args={arguments} error={exc}")
            return {"error": str(exc)}

    def get_balance(self) -> dict:
        """Return placeholder wallet balance view until a dedicated workflow is added."""
        return {
            "usdc": 0,
            "weth": 0,
            "locked_usdc": 0,
            "contract_address": CONTRACT_ADDRESS,
            "usdc_address": USDC_ADDRESS,
            "network": NETWORK,
        }
