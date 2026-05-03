"""First-time setup: duplicate Jerry's KeeperHub workflows into user's org."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
import requests

KEEPERHUB_BASE_URL = "https://app.keeperhub.com/api"
CONFIG_FILE = ".loaf_config.json"

# Jerry's public source workflow IDs.
SOURCE_WORKFLOW_IDS = {
    "register_profile":  "624ntozctk1q1hybl87r7",
    "post_job":          "gwwrxgf4wvhezhj5siylw",
    "approve_usdc":      "0vhloci0din084kgbw7k2",
    "accept_bid":        "20kxns9l73c6bbcdpe4wl",
    "assign_verifier":   "ijsfk5fba1kvr4yyd7e1y",
    "submit_work":       "us82nekq92mvbnetyozh0",
    "submit_verdict":    "1rpwzxwsnxbavqtyc7016",
    "claim_expired":     "cydkhsjz9aufk3nzbhbri",
    "update_axl_key":    "k20qzuz05kqa58q89hdx5",
    "get_job":           "o7e48t9r9vdty8aille1e",
    "get_profile":       "uwv8e2vnt6mnwuw3xft9v",
    "get_profile_addr":  "5dru0q6eh07hrlac140xd",
    "get_profile_id":    "hljvs32qovqcizq3rdcgr",
    "get_jobs_by_state": "ztz13mfa6akrqojrehc8a",
    "get_verifier_ids":  "jutp9gi9gku9axgnfp71p",
    "get_job_count":     "v5bknqna5ge1n2hjqbyy2",
}


class LoafSetup:
    def __init__(self):
        api_key = os.getenv("KEEPERHUB_API_KEY")
        if not api_key:
            print("[setup] ❌ missing KEEPERHUB_API_KEY. Add it to .env or export it before running setup.")
            exit(1)

        self.base_url = KEEPERHUB_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.workflow_ids: dict = {}
        self.project_id: str | None = None
        self.wallet_address: str | None = None
        self.wallet_id: str | None = None

    def run(self):
        """
        Full setup sequence.
        If .loaf_config.json already exists → ask user what to do.
        """
        config_path = Path(CONFIG_FILE)
        
        if config_path.exists():
            print("[setup] ⚠️  loaf-sizzler is already configured.")
            print("[setup] existing config found at .loaf_config.json")
            print()
            response = input("[setup] do you want to reconfigure? (yes/no): ").strip().lower()
            
            if response != "yes":
                print("[setup] setup cancelled. Run: loaf-sizzler start")
                return
            
            # user wants to reconfigure
            # clean up old workflows first
            self._cleanup_old_workflows()
        
        # continue with normal setup
        print("[setup] starting loaf-sizzler KeeperHub setup...")
        self._verify_api_key()
        try:
            self.project_id = self._create_project()
        except Exception:
            self.project_id = None

        self._duplicate_all()
        if self.project_id:
            for wf in list(self.workflow_ids.values()):
                try:
                    self._patch_workflow(wf, self.project_id)
                except Exception:
                    pass
        
        # Enable all workflows for webhook triggers
        print("[setup] enabling workflows for webhook triggers...")
        for wf_id in self.workflow_ids.values():
            try:
                self._enable_workflow(wf_id)
            except Exception:
                pass

        self._save_config()
        self._print_summary()

    def _cleanup_old_workflows(self):
        """
        Load old .loaf_config.json.
        Delete all previously duplicated workflows.
        Delete old project.
        Print progress.
        """
        print("[setup] cleaning up old workflows...")
        
        try:
            with open(CONFIG_FILE) as f:
                old_config = json.load(f)
            
            # delete old workflows
            for name, wf_id in old_config.get("workflow_ids", {}).items():
                if wf_id:
                    response = requests.delete(
                        f"{self.base_url}/workflows/{wf_id}?force=true",
                        headers=self.headers,
                        timeout=20
                    )
                    if response.status_code == 200:
                        print(f"[setup] deleted {name} ✅")
                    else:
                        print(f"[setup] could not delete {name} ⚠️")
            
            # delete old project
            old_project_id = old_config.get("project_id")
            if old_project_id:
                requests.delete(
                    f"{self.base_url}/projects/{old_project_id}",
                    headers=self.headers,
                    timeout=20
                )
                print("[setup] deleted old project ✅")
        
        except Exception as e:
            print(f"[setup] cleanup warning: {e}")
            print("[setup] continuing with fresh setup...")

    def _verify_api_key(self):
        """
        Verify API key and fetch Para wallet address.
        
        GET /api/user/wallet
        
        If hasWallet is False → print instructions and exit.
        If hasWallet is True → store wallet address and print it.
        """
        response = requests.get(
            f"{self.base_url}/user/wallet",
            headers=self.headers,
            timeout=30
        )
        
        if response.status_code == 401:
            print("[setup] ❌ invalid API key. Get yours at app.keeperhub.com → Settings → API Keys")
            exit(1)
        
        if response.status_code != 200:
            print(f"[setup] ❌ KeeperHub connection failed: {response.status_code}")
            exit(1)
        
        data = response.json()
        
        if not data.get("hasWallet"):
            print("[setup] ❌ no Para wallet found on this account.")
            print("[setup] create one at app.keeperhub.com → Settings → Wallet")
            print("[setup] fund it with Sepolia ETH for gas before continuing.")
            exit(1)
        
        self.wallet_address = data["walletAddress"]
        self.wallet_id = data["walletId"]
        
        print(f"[setup] ✅ API key valid")
        print(f"[setup] ✅ Para wallet: {self.wallet_address}")
        print(f"[setup] ✅ wallet ID: {self.wallet_id}")

    def _create_project(self) -> str | None:
        """Attempt to create a 'loaf' project. If not supported, return None."""
        print("[setup] creating loaf project in your org (if supported)...")
        try:
            payload = {"name": "loaf", "description": "Loaf workflows"}
            r = requests.post(f"{self.base_url}/projects", json=payload, headers=self.headers, timeout=30)
            if r.status_code in (200, 201):
                body = r.json() if r.text.strip() else {}
                project_id = body.get("id") or body.get("projectId")
                print(f"[setup] ✅ created project: {project_id}")
                return project_id
            print("[setup] projects API not available or creation skipped")
            return None
        except Exception:
            return None

    def _duplicate_workflow(self, name: str, source_id: str) -> str:
        print(f"[setup] duplicating {name}...", end=" ")
        try:
            r = requests.post(f"{self.base_url}/workflows/{source_id}/duplicate", headers=self.headers, timeout=60)
            if r.status_code not in (200, 201):
                print("❌")
                raise RuntimeError(f"duplicate failed: {r.status_code}")
            body = r.json() if r.text.strip() else {}
            new_id = body.get("id") or body.get("workflowId") or body.get("_id")
            if not new_id:
                print("❌")
                raise RuntimeError("missing workflow id in duplicate response")
            print("✅")
            return str(new_id)
        except Exception as e:
            print(f"[setup] error duplicating {name}: {e}")
            raise

    def _enable_workflow(self, workflow_id: str):
        """Enable workflow (required for webhook trigger)."""
        print(f"[setup] enabling {workflow_id}...", end=" ")
        try:
            r = requests.patch(
                f"{self.base_url}/workflows/{workflow_id}",
                json={"enabled": True},
                headers=self.headers,
                timeout=30
            )
            if r.status_code in (200, 201):
                print("✅")
                return r.json() if r.text.strip() else {}
            else:
                print("⚠️")
                return {}
        except Exception as e:
            print(f"⚠️ {e}")
            return {}

    def _patch_workflow(self, workflow_id: str, project_id: str):
        try:
            requests.patch(
                f"{self.base_url}/workflows/{workflow_id}",
                json={"projectId": project_id},
                headers=self.headers,
                timeout=20,
            )
        except Exception:
            pass

    def _duplicate_all(self):
        total = len(SOURCE_WORKFLOW_IDS)
        print(f"[setup] duplicating {total} workflows into your org...")
        for name, src in SOURCE_WORKFLOW_IDS.items():
            try:
                new_id = self._duplicate_workflow(name, src)
                self.workflow_ids[name] = new_id
            except Exception:
                self.workflow_ids[name] = None

    def _save_config(self):
        data = {
            "workflow_ids": self.workflow_ids,
            "project_id": self.project_id,
            "wallet_address": self.wallet_address,
            "wallet_id": self.wallet_id,
            "setup_at": datetime.utcnow().isoformat() + "Z",
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[setup] config saved to {CONFIG_FILE}")

    def _print_summary(self):
        succeeded = sum(1 for v in self.workflow_ids.values() if v)
        print("\n[loaf-sizzler] setup complete!")
        print("─────────────────────────────")
        print(f"✅ {succeeded} workflows duplicated into your org")
        print(f"✅ config saved to {CONFIG_FILE}")
        print("\nRun: loaf-sizzler start")
