"""CLI entry point for loaf-sizzler."""
import argparse
import os
import signal
import sys

import requests

from loaf_sizzler.axl_client import AxlClient
from loaf_sizzler.config import load_project_env
from loaf_sizzler.contract_client import ContractClient
from loaf_sizzler.server import MCPServer
from loaf_sizzler.storage import create_storage



# Default configuration
MCP_SERVER_PORT = 7100
MCP_ROUTER_URL = "http://localhost:9003"
AXL_NODE_URL = "http://localhost:9002"

# Required environment variables
REQUIRED = [
    "KEEPERHUB_API_KEY",
    "CONTRACT_ADDRESS",
    "AXL_NODE_URL",
    "MCP_ROUTER_URL",
]


class LoafSizzler:
    """Main application class for loaf-sizzler runtime."""

    def __init__(
        self,
        port=7100,
        axl_url=None,
        router_url=None,
        storage_backend="memory",
        db_path="loaf.db",
    ):
        """Initialize loaf-sizzler with configuration."""
        self.port = port
        self.axl_url = axl_url
        self.router_url = router_url
        self.storage_backend = storage_backend
        self.db_path = db_path
        self.storage = None
        self.axl = None
        self.contract = None
        self.server = None

    def start(self):
        """Execute full startup sequence."""
        try:
            self._setup_signal_handlers()

            print("[loaf-sizzler] loading environment...")
            self._load_env()

            print("[loaf-sizzler] initializing storage...")
            self.storage = create_storage(self.storage_backend, self.db_path)

            print(f"[loaf-sizzler] connecting to AXL node at {self.axl_url}...")
            self.axl = AxlClient(self.axl_url)
            print(f"[loaf-sizzler] AXL public key: {self.axl.get_own_key()}")

            print("[loaf-sizzler] connecting to KeeperHub...")
            self.contract = ContractClient(self.axl, self.storage)
            self.contract.setup()
            if self.contract.config and self.contract.config.wallet_address:
                print(f"[loaf-sizzler] wallet: {self.contract.config.wallet_address}")

            print(f"[loaf-sizzler] starting MCP server on port {self.port}...")
            self.server = MCPServer(
                self.axl,
                self.contract,
                self.storage,
                port=self.port,
            )

            print(f"[loaf-sizzler] registering with MCP router at {self.router_url}...")
            self._register()

            print(f"[loaf-sizzler] ready. agents can connect to http://localhost:{self.port}/mcp")
            self.server.start()

        except Exception as e:
            print(f"[loaf-sizzler] error during startup: {e}", file=sys.stderr)
            self._shutdown()
            sys.exit(1)

    def _load_env(self):
        """Validate all required environment variables and config."""
        env_path = load_project_env()
        if env_path:
            print(f"[loaf-sizzler] loaded environment from {env_path}")

        self.axl_url = self.axl_url or os.getenv("AXL_NODE_URL")
        self.router_url = self.router_url or os.getenv("MCP_ROUTER_URL")

        missing = []
        required_values = {
            "KEEPERHUB_API_KEY": os.getenv("KEEPERHUB_API_KEY"),
            "CONTRACT_ADDRESS": os.getenv("CONTRACT_ADDRESS"),
            "AXL_NODE_URL": self.axl_url,
            "MCP_ROUTER_URL": self.router_url,
        }
        for var, value in required_values.items():
            if not value:
                missing.append(var)

        if missing:
            print(
                f"[loaf-sizzler] missing required environment variables: {', '.join(missing)}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Ensure workflow config exists
        try:
            from loaf_sizzler.config import LoafConfig

            if not LoafConfig().is_setup():
                print("[loaf-sizzler] ❌ not configured. Run: loaf-sizzler setup")
                sys.exit(1)
        except SystemExit:
            raise
        except Exception:
            print("[loaf-sizzler] ❌ config check failed — run: loaf-sizzler setup", file=sys.stderr)
            sys.exit(1)

    def _register(self):
        """Register loaf-sizzler service with MCP router."""
        try:
            requests.post(
                f"{self.router_url}/register",
                json={
                    "service": "loaf-sizzler",
                    "endpoint": f"http://127.0.0.1:{self.port}/mcp",
                },
                timeout=5,
            )
        except Exception as e:
            print(f"[loaf-sizzler] warning: registration failed: {e}", file=sys.stderr)

    def _deregister(self):
        """Deregister loaf-sizzler from MCP router."""
        try:
            requests.delete(
                f"{self.router_url}/register/loaf-sizzler",
                timeout=5,
            )
        except Exception as e:
            print(f"[loaf-sizzler] warning: deregistration failed: {e}", file=sys.stderr)

    def _setup_signal_handlers(self):
        """Handle SIGINT and SIGTERM for graceful shutdown."""

        def signal_handler(signum, frame):
            self._shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _shutdown(self):
        """Clean shutdown — deregister and cleanup."""
        print("[loaf-sizzler] shutting down...", file=sys.stderr)
        if self.server:
            self._deregister()
        sys.exit(0)


def main():
    """CLI entry point for loaf-sizzler."""
    parser = argparse.ArgumentParser(
        description="loaf-sizzler — portable agent runtime for the Loaf marketplace"
    )
    subparsers = parser.add_subparsers(dest="command")

    # start subcommand
    start_parser = subparsers.add_parser("start", help="Start the loaf-sizzler runtime")
    start_parser.add_argument("--port", type=int, default=7100, help="MCP server port (default: 7100)")
    start_parser.add_argument("--router-url", type=str, default=None, help="MCP router URL (defaults to MCP_ROUTER_URL)")
    start_parser.add_argument("--axl-url", type=str, default=None, help="AXL node URL (defaults to AXL_NODE_URL)")
    start_parser.add_argument(
        "--storage",
        type=str,
        default="memory",
        choices=["memory", "sqlite"],
        help="Storage backend (default: memory)",
    )
    start_parser.add_argument(
        "--db-path",
        type=str,
        default="loaf.db",
        help="SQLite database path (default: loaf.db)",
    )

    # setup subcommand
    setup_parser = subparsers.add_parser(
        "setup",
        help="First time setup — duplicate KeeperHub workflows into your org",
    )

    args = parser.parse_args()

    if args.command == "setup":
        load_project_env()
        from loaf_sizzler.setup import LoafSetup

        setup = LoafSetup()
        setup.run()

    elif args.command == "start":
        sizzler = LoafSizzler(
            port=args.port,
            axl_url=args.axl_url,
            router_url=args.router_url,
            storage_backend=args.storage,
            db_path=args.db_path,
        )
        sizzler.start()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
