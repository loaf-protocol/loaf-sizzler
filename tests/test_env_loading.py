import json
import os
import tempfile
import unittest
from pathlib import Path

from loaf_sizzler.cli import LoafSizzler
from loaf_sizzler.config import load_project_env


class EnvLoadingTest(unittest.TestCase):
    def test_load_project_env_reads_dotenv_from_given_directory(self):
        key = "LOAF_SIZZLER_TEST_ENV"
        old_value = os.environ.pop(key, None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp, ".env").write_text(f"{key}=from-project\n", encoding="utf-8")

                loaded = load_project_env(tmp)

                self.assertEqual(loaded, Path(tmp, ".env"))
                self.assertEqual(os.environ[key], "from-project")
        finally:
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

    def test_start_env_validation_uses_current_working_directory_dotenv(self):
        env_keys = [
            "KEEPERHUB_API_KEY",
            "CONTRACT_ADDRESS",
            "AXL_NODE_URL",
            "MCP_ROUTER_URL",
        ]
        old_env = {key: os.environ.pop(key, None) for key in env_keys}
        old_cwd = Path.cwd()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                project.joinpath(".env").write_text(
                    "\n".join(
                        [
                            "KEEPERHUB_API_KEY=kh_test",
                            "CONTRACT_ADDRESS=0x123",
                            "AXL_NODE_URL=http://axl.example",
                            "MCP_ROUTER_URL=http://router.example",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                project.joinpath(".loaf_config.json").write_text(
                    json.dumps({"workflow_ids": {}}),
                    encoding="utf-8",
                )

                os.chdir(project)
                sizzler = LoafSizzler(axl_url=None, router_url=None)
                sizzler._load_env()

                self.assertEqual(sizzler.axl_url, "http://axl.example")
                self.assertEqual(sizzler.router_url, "http://router.example")
        finally:
            os.chdir(old_cwd)
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
