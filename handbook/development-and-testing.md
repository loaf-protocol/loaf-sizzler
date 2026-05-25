# Development And Testing

This page covers local development practices for this repository.

## Code Layout

```text
loaf_sizzler/
  axl_client.py          AXL node client
  cli.py                 CLI entry point
  config.py              .env and .loaf_config.json loading
  contract_client.py     KeeperHub workflow client
  server.py              Flask MCP server
  setup.py               KeeperHub workflow duplication setup
  storage/               storage interfaces and backends
  tools/                 MCP tool implementations
tests/
  test_*.py              unit tests
  e2e_test.py            external end-to-end script
```

There is also a legacy-looking `loaf_sizzler/storage.py`. Current runtime code
imports the `loaf_sizzler.storage` package, not that standalone module.

## Local Test Commands

Run the unit suite:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Run a syntax compile pass:

```bash
python -m compileall -q loaf_sizzler tests
```

If `pytest` is installed, the unit tests can also be run with:

```bash
python -m pytest -q
```

The project does not require `pytest` for the existing unit suite.

## End-To-End Script

The end-to-end script is:

```bash
python tests/e2e_test.py
```

It requires two running `loaf-sizzler` instances, two reachable AXL nodes, and
valid on-chain/profile/job data.

The script can be configured with environment variables:

```bash
LOAF_E2E_BASE_A=http://localhost:7100/mcp
LOAF_E2E_BASE_B=http://localhost:7101/mcp
LOAF_E2E_AXL_A=<worker axl key>
LOAF_E2E_AXL_B=<poster/verifier axl key>
LOAF_E2E_PROFILE_A=<worker profile id>
LOAF_E2E_PROFILE_B=<verifier profile id>
LOAF_E2E_JOB_ID=<numeric job id>
LOAF_E2E_PROPOSED_AMOUNT=1000000
```

Do not treat the e2e script as a hermetic test. It exercises live services and
external state.

## Tool Implementation Pattern

Each tool under `loaf_sizzler/tools/` should stay small. The usual pattern is:

1. Validate or read required arguments.
2. Call the contract client, AXL client, or storage backend.
3. Return a JSON-serializable dictionary.

The server wraps returned dictionaries into MCP-compatible `content` and
`structuredContent` fields.

## Adding A New Tool

To add a new MCP tool:

1. Create a tool implementation in `loaf_sizzler/tools/`.
2. Import it in `loaf_sizzler/server.py`.
3. Add a schema entry to `TOOL_DEFINITIONS`.
4. Add a dispatch branch in `MCPServer._call_tool()`.
5. Add focused unit tests for success and failure behavior.
6. Update `handbook/mcp-tools.md` if the tool is user-facing.

## Amount Handling

Use `parse_usdc_amount()` from `contract_client.py` for USDC input conversion.

Rules:

- Integer values and integer strings are treated as raw 6-decimal USDC units.
- Decimal values are treated as human USDC amounts.
- Values below USDC precision are rejected.
- Zero, negative values, and booleans are rejected.

Examples:

```text
1        -> 1 raw unit
"1000000" -> 1000000 raw units
"1.25"  -> 1250000 raw units
"0.000001" -> 1 raw unit
```

## Current Unit Test Coverage

The unit tests cover:

- MCP initialization and tool listing.
- MCP tool call wrapping and unknown-tool errors.
- USDC amount parsing.
- Environment loading.
- Job state listing and fallback scanning.
- Output authorization.
- Registration recovery.
- Balance response shape.

