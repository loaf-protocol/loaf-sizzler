"""Contract client via KeeperHub marketplace workflows."""

from __future__ import annotations

import os
import time
import json
from decimal import Decimal, InvalidOperation

import requests

from loaf_sizzler.config import LoafConfig


JOB_STATES = {
    "open": 0,
    "active": 1,
    "in_review": 2,
    "review": 2,
    "settled": 3,
    "resolved": 3,
    "expired": 4,
    "cancelled": 5,
}
JOB_STATE_NAMES = {value: key for key, value in JOB_STATES.items() if key not in {"review", "resolved"}}
USDC_DECIMALS = 6
USDC_SCALE = Decimal(10) ** USDC_DECIMALS


def parse_usdc_amount(value, field_name: str = "amount") -> int:
    """
    Convert user-facing USDC decimals to raw 6-decimal units.
    Integer values and integer strings are treated as already-raw units.
    Decimal strings/floats are treated as USDC amounts.
    """
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a USDC amount, not a boolean")

    if isinstance(value, int):
        raw = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError(f"{field_name} is required")

        try:
            decimal_value = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"{field_name} must be a valid USDC amount") from exc

        if decimal_value == decimal_value.to_integral_value() and "." not in text and "e" not in text.lower():
            raw = int(decimal_value)
        else:
            raw_decimal = decimal_value * USDC_SCALE
            if raw_decimal != raw_decimal.to_integral_value():
                raise ValueError(
                    f"{field_name} is below USDC precision or has too many decimals; "
                    f"minimum non-zero amount is 0.000001 USDC"
                )
            raw = int(raw_decimal)

    if raw <= 0:
        raise ValueError(f"{field_name} must be greater than 0")
    return raw


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
            self._wallet_address = self.config.wallet_address
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
        if isinstance(payload, dict):
            for key in ("profileId", "profile_id", "id"):
                if payload.get(key) is not None:
                    return int(payload[key])
            result = payload.get("result")
            if isinstance(result, list) and result:
                return int(result[0])
        elif isinstance(payload, list) and payload:
            return int(payload[0])
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
        try:
            self._profile_id = self._register()
        except RuntimeError as exc:
            if "AlreadyRegistered" not in str(exc):
                raise
            profile = self.get_profile_by_address()
            if not profile.get("exists"):
                raise
            self._profile_id = int(profile["id"])
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
        lookup_address = address or self._wallet_address or (self.config.wallet_address if self.config else None)
        inputs = {}
        if lookup_address:
            inputs["addr"] = lookup_address

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
        return self._normalize_job_payload(result, int(job_id))

    def _get_job_ids_by_state(self, state: int) -> list[int] | dict:
        result = self._run_workflow("get_jobs_by_state", {"state": int(state)})
        if result.get("error"):
            return result

        ids = result.get("jobIds") or result.get("ids") or result.get("jobs") or []
        if not ids and isinstance(result.get("result"), list):
            ids = result["result"]
        if isinstance(ids, list):
            parsed = []
            for item in ids:
                if isinstance(item, (list, tuple)) and item:
                    parsed.append(int(item[0]))
                else:
                    parsed.append(int(item))
            return parsed
        return []

    def _normalize_job_state(self, state: int | str | None) -> int | str:
        if state is None:
            return JOB_STATES["open"]

        if isinstance(state, int):
            return state

        state_text = str(state).strip().lower().replace("-", "_").replace(" ", "_")
        if state_text == "all":
            return "all"
        if state_text.isdigit():
            return int(state_text)
        if state_text in JOB_STATES:
            return JOB_STATES[state_text]

        allowed = ", ".join(sorted({*JOB_STATES.keys(), "all"}))
        raise ValueError(f"unknown job state '{state}'. Use one of: {allowed}")

    def _normalize_job_payload(self, payload: dict, fallback_job_id: int | None = None) -> dict:
        values = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            return payload

        job = {
            **payload,
            "jobId": fallback_job_id,
            "posterProfileId": int(values[0]) if len(values) > 0 else None,
            "workerProfileId": int(values[1]) if len(values) > 1 else 0,
            "verifierIds": values[2] if len(values) > 2 else [],
            "criteria": values[3] if len(values) > 3 else "",
            "outputHash": values[4] if len(values) > 4 else "",
            "workerAmount": int(values[5]) if len(values) > 5 else 0,
            "verifierFeeEach": int(values[6]) if len(values) > 6 else 0,
            "verifierCount": int(values[7]) if len(values) > 7 else 0,
            "quorumThreshold": int(values[8]) if len(values) > 8 else 0,
            "minVerifierScore": int(values[9]) if len(values) > 9 else 0,
            "acceptedWorkerAmount": int(values[10]) if len(values) > 10 else 0,
            "expiresAt": int(values[12]) if len(values) > 12 else 0,
            "state": int(values[13]) if len(values) > 13 else None,
        }
        if job["state"] is not None:
            job["stateName"] = JOB_STATE_NAMES.get(job["state"], str(job["state"]))
        return job

    def _job_matches_state(self, job: dict, state: int) -> bool:
        try:
            return int(job.get("state")) == int(state)
        except Exception:
            return False

    def _scan_jobs_by_state(self, state: int | None = None, limit: int = 100) -> list:
        jobs = []
        for job_id in range(1, limit + 1):
            job = self.get_job(job_id)
            if not isinstance(job, dict) or job.get("error"):
                continue
            if state is None or self._job_matches_state(job, state):
                jobs.append(job)
        return self._enrich_job_records(jobs)

    def _enrich_job_records(self, jobs: list[dict]) -> list:
        enriched = []
        for job in jobs:
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

            enriched.append(job)
        return enriched

    def _enrich_jobs(self, ids: list[int]) -> list:
        jobs = []
        for job_id in ids:
            job = self.get_job(job_id)
            if not isinstance(job, dict) or job.get("error"):
                continue
            jobs.append(job)
        return self._enrich_job_records(jobs)

    def list_jobs(self, state: int | str | None = None) -> list | dict:
        """
        Get jobs by state. Defaults to OPEN.
        Calls get_jobs_by_state then get_job for each ID.
        Enriches each job with poster axlPublicKey from profile.
        Returns list of job dicts.
        """
        try:
            normalized_state = self._normalize_job_state(state)
        except ValueError as exc:
            return {"error": str(exc)}

        if normalized_state == "all":
            all_jobs = []
            seen = set()
            for state_id in sorted(set(JOB_STATES.values())):
                ids = self._get_job_ids_by_state(state_id)
                if isinstance(ids, dict):
                    continue
                for job in self._enrich_jobs(ids):
                    job_id = job.get("jobId") or job.get("job_id") or job.get("id")
                    if job_id is not None and job_id in seen:
                        continue
                    if job_id is not None:
                        seen.add(job_id)
                    all_jobs.append(job)
            if not all_jobs:
                return self._scan_jobs_by_state(None)
            return all_jobs

        ids = self._get_job_ids_by_state(normalized_state)
        if isinstance(ids, dict):
            return ids
        jobs = self._enrich_jobs(ids)
        if not jobs:
            return self._scan_jobs_by_state(normalized_state)
        return jobs

    def list_review_jobs(self) -> list | dict:
        """
        Get IN_REVIEW jobs (state=2).
        Compatibility alias for list_jobs(state="in_review").
        """
        return self.list_jobs("in_review")

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

        try:
            worker_amount_raw = parse_usdc_amount(worker_amount, "worker_amount")
            verifier_fee_each_raw = parse_usdc_amount(verifier_fee_each, "verifier_fee_each")
        except ValueError as exc:
            return {"error": str(exc)}

        result = self._run_workflow(
            "post_job",
            {
                "criteria": criteria,
                "WorkAmount": worker_amount_raw,
                "VerifierFeeEach": verifier_fee_each_raw,
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
        try:
            agreed_worker_amount_raw = parse_usdc_amount(agreed_worker_amount, "agreed_worker_amount")
        except ValueError as exc:
            return {"error": str(exc)}

        total = agreed_worker_amount_raw + (verifier_fee_each * verifier_count)

        approval = self.approve_usdc(total)
        if approval.get("error"):
            return approval

        result = self._run_workflow(
            "accept_bid",
            {
                "jobId": int(job_id),
                "workerProfileId": int(worker_profile_id),
                "agreedWorkerAmount": agreed_worker_amount_raw,
            },
        )
        if result.get("error"):
            return result

        return {"status": "accepted", "tx_hash": self._extract_tx_hash(result)}

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

        return {"status": "assigned", "tx_hash": self._extract_tx_hash(result)}

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

        return {"status": "submitted", "tx_hash": self._extract_tx_hash(result)}

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

        return {"status": "verdict_sent", "tx_hash": self._extract_tx_hash(result)}

    def approve_usdc(self, amount: int) -> dict:
        """
        Call loaf-approve-usdc workflow.
        Called internally by accept_bid.
        Return { tx_hash }
        """
        try:
            amount_raw = parse_usdc_amount(amount, "amount")
        except ValueError as exc:
            return {"error": str(exc)}

        result = self._run_workflow(
            "approve_usdc",
            {
                "token": self.usdc_address,
                "spender": self.contract_address,
                "amount": amount_raw,
                "network": self.network,
            },
        )
        if result.get("error"):
            return result

        return {"status": "approved", "tx_hash": self._extract_tx_hash(result)}

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

        return {"status": "claimed", "tx_hash": self._extract_tx_hash(result)}

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

        return {"status": "updated", "tx_hash": self._extract_tx_hash(result)}

    def get_balance(self) -> dict:
        """
        Get USDC balance of user's Para wallet.
        Returns configured wallet metadata.
        """
        wallet_address = self._wallet_address
        if not wallet_address and self.config:
            wallet_address = self.config.wallet_address
            self._wallet_address = wallet_address

        if not wallet_address:
            return {"error": "wallet_address missing from .loaf_config.json. Run: loaf-sizzler setup"}

        return {
            "usdc": 0,
            "wallet_address": wallet_address,
            "usdc_address": self.usdc_address,
            "network": self.network,
            "source": ".loaf_config.json",
            "note": "USDC balance lookup is not implemented yet; wallet address is loaded from local setup config.",
        }
