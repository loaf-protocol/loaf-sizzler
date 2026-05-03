"""Contract client via KeeperHub marketplace workflows."""

from __future__ import annotations

import os
import time
import json

import requests

from loaf_sizzler.config import LoafConfig


class ContractClient:
    def __init__(self, axl_client, storage):
        # Read environment variables after load_dotenv() has run in cli.py
        api_key = os.getenv("KEEPERHUB_API_KEY")
        self.contract_address = os.getenv("CONTRACT_ADDRESS", "0x8De32D82714153E5a0f07Cc10924A677C6dD4b5A")
        self.usdc_address = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
        self.network = "11155111"
        self.base_url = "https://app.keeperhub.com/api"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.axl_client = axl_client
        self.storage = storage
        self._profile_id = None
        self._wallet_address = None
        # load local workflow config (duplicated into user's org)
        try:
            self.config = LoafConfig()
        except SystemExit:
            # LoafConfig will exit with helpful message if missing; re-raise
            raise
        except Exception:
            self.config = None

    def setup(self):
        """
        Called once from cli.py.
        Verify workflow config and print loaded workflows.
        """
        print("[keeperhub] loading workflow config...")
        if not self.config:
            print("[keeperhub] workflow config not loaded — run loaf-sizzler setup")
            return

        count = 0
        for name, wf_id in self.config.workflow_ids.items():
            if wf_id:
                print(f"[keeperhub] {name}: {str(wf_id)[:8]}...")
                count += 1
            else:
                print(f"[keeperhub] {name}: missing — run loaf-sizzler setup")
        if count:
            print(f"[keeperhub] {count} workflows loaded")

    def _run_workflow(self, slug_name: str, inputs: dict | None = None) -> dict:
        args = inputs or {}
        try:
            data = self._execute(slug_name, args)
        except Exception as exc:
            print(f"[keeperhub] workflow failure: name={slug_name} inputs={args} error={exc}")
            return {"error": str(exc)}

        if isinstance(data, dict):
            # try common shapes
            if isinstance(data.get("output"), dict):
                return data["output"]
            if isinstance(data.get("result"), dict):
                return data["result"]
            if isinstance(data.get("data"), dict):
                return data["data"]
            return data
        return {"result": data}

    def _clean_inputs(self, inputs: dict) -> dict:
        """
        KeeperHub ABI validator expects numeric args as strings.
        """
        numeric_fields = {
            "jobId", "profileId", "state", "workerProfileId",
            "verifierProfileId", "agreedWorkerAmount", "WorkAmount",
            "VerifierFeeEach", "VerifierCount", "QuorumThreshold",
            "MinimumVerifierScore", "expiresAt", "amount"
        }
        cleaned = {}
        for key, value in inputs.items():
            if key in numeric_fields:
                cleaned[key] = str(value)
            else:
                cleaned[key] = value
        return cleaned

    def _execute(self, workflow_name: str, inputs: dict | None = None) -> dict:
        """Execute a duplicated workflow by webhook and poll until complete."""
        if not self.config:
            raise RuntimeError("workflow config not loaded")

        wf_id = self.config.get_workflow_id(workflow_name)
        payload = self._clean_inputs(inputs or {})
        
        wfb_key = os.getenv("KEEPERHUB_WFB_KEY")
        if not wfb_key:
            raise RuntimeError("KEEPERHUB_WFB_KEY not set in environment")
        
        webhook_headers = {
            "Authorization": f"Bearer {wfb_key}",
            "Content-Type": "application/json",
        }
        
        r = requests.post(f"{self.base_url}/workflows/{wf_id}/webhook", json=payload, headers=webhook_headers, timeout=30)
        print(f"[keeperhub] webhook response: status={r.status_code} body={r.text}")
        if r.status_code >= 400:
            raise RuntimeError(f"execute failed: {r.status_code} {r.text}")

        data = r.json() if r.text.strip() else {}
        print(f"[keeperhub] webhook data: {data}")
        status = data.get("status")
        if status in ("pending", "running"):
            execution_id = data.get("executionId") or data.get("id")
            if not execution_id:
                raise RuntimeError("execution started but no executionId returned")
            return self._poll(execution_id)
        return data

    def _poll(self, execution_id: str) -> dict:
        """
        Poll execution status then fetch logs for result.
        
        Status endpoint:
        GET /api/workflows/executions/{executionId}/status
        
        Logs endpoint (for actual output):
        GET /api/workflows/executions/{executionId}/logs
        """
        for i in range(40):
            time.sleep(2)
            r = requests.get(
                f"{self.base_url}/workflows/executions/{execution_id}/status",
                headers=self.headers,
                timeout=30
            )
            if r.status_code >= 400:
                continue
            
            data = r.json() if r.text.strip() else {}
            status = data.get("status")
            print(f"[poll] attempt {i+1}: status={status}")
            
            if status in ("success", "error", "cancelled"):
                # fetch logs to get actual output
                logs_r = requests.get(
                    f"{self.base_url}/workflows/executions/{execution_id}/logs",
                    headers=self.headers,
                    timeout=30
                )
                logs_data = logs_r.json() if logs_r.text.strip() else {}
                print(f"[poll] logs_data keys: {list(logs_data.keys())}")
                
                # KeeperHub webhook response has "execution" at top level
                if "execution" in logs_data:
                    execution = logs_data["execution"]
                    output = execution.get("output")
                    error = execution.get("error")
                    exec_status = execution.get("status")
                    
                    print(f"[poll] execution status: {exec_status}, output: {str(output)[:200]}, error: {str(error)[:200]}")
                    
                    if exec_status == "error":
                        return {"error": error or "unknown error"}
                    
                    if output is not None:
                        return output
                    
                    return execution
                
                # fallback: return logs_data as-is
                print(f"[poll] returning full logs_data")
                return logs_data
        
        raise RuntimeError("execution timeout")

    def _extract_tx_hash(self, payload: dict) -> str | None:
        for key in ("tx_hash", "txHash", "transactionHash", "hash"):
            value = payload.get(key)
            if value:
                return str(value)
        return None

    def _extract_wallet_address(self, payload: object) -> str | None:
        if isinstance(payload, dict):
            for key in ("wallet", "walletAddress", "address", "paraWallet", "evmAddress"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
            for value in payload.values():
                found = self._extract_wallet_address(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = self._extract_wallet_address(item)
                if found:
                    return found
        return None

    def _extract_profile_id(self, payload: dict) -> int | None:
        for key in ("profileId", "profile_id", "id"):
            if payload.get(key) is not None:
                return int(payload[key])
        return None

    def _ensure_registered(self) -> int:
        """
        Check storage for cached profileId first.
        If not cached check contract via get_profile_by_address.
        If not registered register automatically.
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
            self._profile_id = int(profile["id"])
            self.storage.set_agent_data("profile_id", str(self._profile_id))
            return self._profile_id

        print("[loaf-sizzler] first time setup — registering agent profile...")
        self._profile_id = self._register()
        self.storage.set_agent_data("profile_id", str(self._profile_id))
        print(f"[loaf-sizzler] profile registered: id={self._profile_id}")
        return self._profile_id

    def _register(self) -> int:
        """
        Register agent profile via KeeperHub marketplace workflow.
        Gets own AXL key from axl_client.
        Returns profileId from workflow output.
        """
        axl_key = self.axl_client.get_own_key()
        result = self._run_workflow("register_profile", {"axlPublicKey": axl_key})
        if result.get("error"):
            raise RuntimeError(result["error"])

        profile_id = self._extract_profile_id(result)
        if profile_id is None:
            raise RuntimeError(f"profileId missing from register_profile result: {result}")
        return profile_id

    def get_profile_by_address(self, address: str = None) -> dict:
        """
        Get profile for address.
        If address None → use Para wallet address from KeeperHub.
        Returns profile dict with exists field.
        If not found returns { "exists": False }
        """
        inputs = {}
        if address:
            inputs["addr"] = address

        result = self._run_workflow("get_profile_addr", inputs)
        if result.get("error"):
            return {"error": result["error"]}

        profile_id = self._extract_profile_id(result)
        if profile_id is None:
            return {"exists": False}

        result["id"] = profile_id
        result["exists"] = True
        return result

    def get_profile_by_address_or_axl_key(self, value: str) -> dict | None:
        """Best-effort profile lookup for address-like identifiers."""
        if not value:
            return None

        if isinstance(value, str) and value.startswith("0x"):
            profile = self.get_profile_by_address(value)
            if profile.get("exists"):
                return profile

        return None

    def is_assigned_verifier(self, job_id: int, profile_id: int) -> bool:
        """
        Check verifierIds for job.
        Return True if profile_id is in the list.
        """
        verifier_ids = self.get_verifier_ids(job_id)
        return profile_id in verifier_ids

    def get_profile(self, profile_id: int) -> dict:
        """Get profile by profileId."""
        result = self._run_workflow("get_profile", {"profileId": int(profile_id)})
        if result.get("error"):
            return result

        result.setdefault("id", int(profile_id))
        result.setdefault("exists", True)
        return result

    def get_job(self, job_id: int) -> dict:
        """Get job by jobId."""
        result = self._run_workflow("get_job", {"jobId": int(job_id)})
        if result.get("error"):
            return result
        return result

    def _get_job_ids_by_state(self, state: int) -> list[int] | dict:
        result = self._run_workflow("get_jobs_by_state", {"state": int(state)})
        if result.get("error"):
            return result

        ids = result.get("jobIds") or result.get("ids") or result.get("jobs") or []
        if isinstance(ids, list):
            return [int(job_id) for job_id in ids]
        return []

    def list_jobs(self) -> list:
        """
        Get OPEN jobs (state=0).
        Calls get_jobs_by_state then get_job for each ID.
        Enriches each job with poster axlPublicKey from profile.
        Returns list of job dicts.
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
            if poster_profile_id is not None:
                profile = self.get_profile(int(poster_profile_id))
                axl_key = profile.get("axlPublicKey") or profile.get("axlKey") or profile.get("axl_key")
                if axl_key:
                    job["poster_axl_key"] = axl_key

            jobs.append(job)
        return jobs

    def list_review_jobs(self) -> list:
        """
        Get IN_REVIEW jobs (state=2).
        Same pattern as list_jobs.
        """
        ids = self._get_job_ids_by_state(2)
        if isinstance(ids, dict):
            return []

        jobs = []
        for job_id in ids:
            job = self.get_job(job_id)
            if isinstance(job, dict) and not job.get("error"):
                poster_profile_id = (
                    job.get("posterProfileId")
                    or job.get("poster_profile_id")
                    or job.get("posterId")
                    or job.get("poster_id")
                )
                if poster_profile_id is not None:
                    profile = self.get_profile(int(poster_profile_id))
                    axl_key = profile.get("axlPublicKey") or profile.get("axlKey") or profile.get("axl_key")
                    if axl_key:
                        job["poster_axl_key"] = axl_key
                jobs.append(job)
        return jobs

    def get_verifier_ids(self, job_id: int) -> list:
        """Get assigned verifier profileIds for a job."""
        result = self._run_workflow("get_verifier_ids", {"jobId": int(job_id)})
        if result.get("error"):
            return []

        verifier_ids = result.get("verifierIds") or result.get("ids") or result.get("profileIds") or []
        if not isinstance(verifier_ids, list):
            return []
        return [int(v) for v in verifier_ids]

    def _get_job_count(self, profile_id: int, role: str) -> int:
        result = self._run_workflow(
            "get_job_count",
            {
                "profileId": int(profile_id),
                "role": role,
            },
        )
        if result.get("error"):
            return 0

        value = result.get("count") or result.get("jobCount") or result.get(role)
        try:
            return int(value)
        except Exception:
            return 0

    def get_reputation(self, profile_id: int) -> dict:
        """
        Get reputation for profileId.
        Returns {
            workerScore, verifierScore, posterScore,
            workerJobs, verifierJobs, posterJobs
        }
        """
        profile = self.get_profile(profile_id)
        if profile.get("error"):
            return profile

        reputation = {
            "workerScore": int(profile.get("workerScore") or 0),
            "verifierScore": int(profile.get("verifierScore") or 0),
            "posterScore": int(profile.get("posterScore") or 0),
            "workerJobs": int(profile.get("workerJobs") or 0),
            "verifierJobs": int(profile.get("verifierJobs") or 0),
            "posterJobs": int(profile.get("posterJobs") or 0),
        }

        # fallback to workflow counts if missing on profile
        if reputation["workerJobs"] == 0:
            reputation["workerJobs"] = self._get_job_count(profile_id, "worker")
        if reputation["verifierJobs"] == 0:
            reputation["verifierJobs"] = self._get_job_count(profile_id, "verifier")
        if reputation["posterJobs"] == 0:
            reputation["posterJobs"] = self._get_job_count(profile_id, "poster")

        return reputation

    def get_output_hash(self, job_id: int) -> str:
        """Get outputHash from job as hex string."""
        job = self.get_job(job_id)
        if job.get("error"):
            return ""

        value = job.get("outputHash") or job.get("output_hash") or ""
        if isinstance(value, bytes):
            return f"0x{value.hex()}"
        if isinstance(value, str):
            return value if value.startswith("0x") else f"0x{value}"
        return ""

    def register_profile(self, axl_key: str) -> dict:
        """Explicit register helper."""
        result = self._run_workflow("register_profile", {"axlPublicKey": axl_key})
        if result.get("error"):
            return result

        profile_id = self._extract_profile_id(result)
        if profile_id is None:
            return {"error": "profileId missing from register_profile result"}

        self._profile_id = profile_id
        self.storage.set_agent_data("profile_id", str(profile_id))
        return {"profileId": profile_id}

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
        Call loaf-post-job workflow.
        Return { job_id, tx_hash }
        NOTE: no USDC approval needed here
        USDC locked at accept_bid
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        result = self._run_workflow(
            "post_job",
            {
                "criteria": criteria,
                "WorkAmount": int(worker_amount),
                "VerifierFeeEach": int(verifier_fee_each),
                "VerifierCount": int(verifier_count),
                "QuorumThreshold": int(quorum_threshold),
                "MinimumVerifierScore": int(min_verifier_score),
                "expiresAt": int(expires_at),
            },
        )
        if result.get("error"):
            return result

        job_id = result.get("jobId") or result.get("job_id")
        tx_hash = self._extract_tx_hash(result)
        return {"job_id": job_id, "tx_hash": tx_hash}

    def accept_bid(self, job_id: int, worker_profile_id: int, agreed_worker_amount: int) -> dict:
        """
        _ensure_registered() first.
        1. calculate total = agreed_worker_amount + (verifierFeeEach * verifierCount)
        2. call loaf-approve-usdc workflow with total amount
        3. call loaf-accept-bid workflow
        Return { tx_hash }
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        job = self.get_job(job_id)
        if job.get("error"):
            return job

        verifier_fee_each = int(job.get("verifierFeeEach") or job.get("verifier_fee_each") or 0)
        verifier_count = int(job.get("verifierCount") or job.get("verifier_count") or 0)
        total = int(agreed_worker_amount) + (verifier_fee_each * verifier_count)

        approval = self.approve_usdc(total)
        if approval.get("error"):
            return approval

        result = self._run_workflow(
            "accept_bid",
            {
                "jobId": int(job_id),
                "workerProfileId": int(worker_profile_id),
                "agreedWorkerAmount": int(agreed_worker_amount),
            },
        )
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def assign_verifier(self, job_id: int, verifier_profile_id: int) -> dict:
        """
        _ensure_registered() first.
        Call loaf-assign-verifier workflow.
        Return { tx_hash }
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        result = self._run_workflow(
            "assign_verifier",
            {
                "jobId": int(job_id),
                "verifierProfileId": int(verifier_profile_id),
            },
        )
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def submit_work(self, job_id: int, output_hash: bytes | str) -> dict:
        """
        _ensure_registered() first.
        Call loaf-submit-work workflow.
        output_hash as hex string.
        Return { tx_hash }
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        if isinstance(output_hash, str):
            normalized_hash = output_hash if output_hash.startswith("0x") else f"0x{output_hash}"
        else:
            normalized_hash = f"0x{output_hash.hex()}"

        result = self._run_workflow(
            "submit_work",
            {
                "jobId": int(job_id),
                "outputHash": normalized_hash,
            },
        )
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def submit_verdict(self, job_id: int, passed: bool) -> dict:
        """
        _ensure_registered() first.
        Call loaf-submit-verdict workflow.
        Return { tx_hash }
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        result = self._run_workflow(
            "submit_verdict",
            {
                "jobId": int(job_id),
                "pass": bool(passed),
            },
        )
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def approve_usdc(self, amount: int) -> dict:
        """
        Call loaf-approve-usdc workflow.
        Called internally by accept_bid.
        Return { tx_hash }
        """
        result = self._run_workflow(
            "approve_usdc",
            {
                "token": self.usdc_address,
                "spender": self.contract_address,
                "amount": int(amount),
                "network": self.network,
            },
        )
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def claim_expired(self, job_id: int) -> dict:
        """
        _ensure_registered() first.
        Call loaf-claim-expired workflow.
        Return { tx_hash }
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        result = self._run_workflow("claim_expired", {"jobId": int(job_id)})
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def update_axl_key(self, new_key: str) -> dict:
        """
        _ensure_registered() first.
        Call loaf-update-axl-key workflow.
        Return { tx_hash }
        """
        try:
            self._ensure_registered()
        except Exception as exc:
            return {"error": str(exc)}

        result = self._run_workflow("update_axl_key", {"axlPublicKey": new_key})
        if result.get("error"):
            return result

        return {"tx_hash": self._extract_tx_hash(result)}

    def get_balance(self) -> dict:
        """
        Get USDC balance of user's Para wallet.
        Returns { usdc, wallet_address }
        """
        return {
            "usdc": 0,
            "wallet_address": self._wallet_address,
        }
