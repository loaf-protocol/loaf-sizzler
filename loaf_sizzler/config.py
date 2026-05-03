import json
import os
from pathlib import Path

CONFIG_FILE = ".loaf_config.json"


def load_project_env(cwd: str | os.PathLike[str] | None = None) -> Path | None:
    """Load .env from the user's current project directory or its parents."""
    from dotenv import load_dotenv

    root = (Path(cwd) if cwd is not None else Path.cwd()).resolve()
    for path in [root, *root.parents]:
        env_path = path / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            return env_path

    return None


class LoafConfig:
    def __init__(self):
        self.workflow_ids = {}
        self.project_id = None
        self.wallet_address = None
        self.wallet_id = None
        self._load()

    def _load(self):
        config_path = Path(CONFIG_FILE)
        if not config_path.exists():
            print("[loaf-sizzler] ❌ config not found. Run: loaf-sizzler setup")
            exit(1)

        with open(config_path) as f:
            data = json.load(f)

        self.workflow_ids = data.get("workflow_ids", {})
        self.project_id = data.get("project_id")
        self.wallet_address = data.get("wallet_address")
        self.wallet_id = data.get("wallet_id")

    def get_workflow_id(self, name: str) -> str:
        wf_id = self.workflow_ids.get(name)
        if not wf_id:
            raise Exception(f"workflow '{name}' not found in config. Run: loaf-sizzler setup")
        return wf_id

    def is_setup(self) -> bool:
        return Path(CONFIG_FILE).exists()
