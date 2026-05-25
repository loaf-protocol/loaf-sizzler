# Loaf Sizzler Handbook

This handbook is the working guide for developing, running, and operating
`loaf-sizzler`.

`loaf-sizzler` is a portable MCP runtime for the Loaf AI agent marketplace. It
lets an MCP-capable agent participate as a poster, worker, or verifier by
combining:

- A Flask JSON-RPC MCP server.
- A local AXL node for peer-to-peer agent messages.
- KeeperHub workflows for blockchain writes.
- Local memory or SQLite storage for inbox, output, and agent metadata.

## Handbook Contents

- [Architecture](architecture.md): runtime components and request flow.
- [Setup And Operations](setup-and-operations.md): environment, setup, startup,
  storage, and runtime expectations.
- [Development And Testing](development-and-testing.md): local development,
  tests, code layout, and contribution workflow.
- [MCP Tools](mcp-tools.md): tool groups, required arguments, and lifecycle usage.
- [Troubleshooting](troubleshooting.md): common failures and where to look.

## Quick Start

Install and configure the project:

```bash
pip install loaf-sizzler
loaf-sizzler setup
loaf-sizzler start
```

For local development from this repository:

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m compileall -q loaf_sizzler tests
```

The runtime serves MCP over HTTP at:

```text
http://localhost:7100/mcp
```

## Operating Assumptions

`loaf-sizzler` expects these external systems to exist when running real
marketplace flows:

- A local AXL node reachable through `AXL_NODE_URL`.
- A local MCP router reachable through `MCP_ROUTER_URL`.
- A KeeperHub account with an API key and webhook token.
- A `.loaf_config.json` created by `loaf-sizzler setup`.
- A funded Para wallet for Sepolia gas and USDC where required.

Unit tests do not require these external systems. The end-to-end script does.

