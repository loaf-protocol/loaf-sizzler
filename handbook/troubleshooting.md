# Troubleshooting

## Startup Fails With Missing Environment Variables

Symptom:

```text
missing required environment variables
```

Check that `.env` exists in the current directory or one of its parents and
contains:

- `KEEPERHUB_API_KEY`
- `CONTRACT_ADDRESS`
- `AXL_NODE_URL`
- `MCP_ROUTER_URL`

`KEEPERHUB_WFB_KEY` is also required for workflow webhook execution.

## Startup Says Setup Has Not Run

Symptom:

```text
not configured. Run: loaf-sizzler setup
```

Run:

```bash
loaf-sizzler setup
```

This creates `.loaf_config.json`. If the file already exists but startup still
fails, run from the project directory that contains the intended config file.

## AXL Public Key Lookup Fails

Likely causes:

- `AXL_NODE_URL` points at the wrong port.
- The local AXL node is not running.
- The AXL node does not expose `/topology`.

Check:

```bash
curl "$AXL_NODE_URL/topology"
```

The response should include `our_public_key`.

## Messages Do Not Arrive In Inbox

Check:

- The target `poster_axl_key`, `worker_axl_key`, or `verifier_axl_key` is
  correct.
- Both agents are registered with the MCP router.
- Both AXL nodes are running and connected.
- The receiving runtime exposes `/mcp`.
- The receiving runtime has not been restarted when using memory storage.

Use:

```json
{
  "name": "get_inbox",
  "arguments": {}
}
```

to inspect received messages.

## KeeperHub Workflow Fails

Likely causes:

- `KEEPERHUB_WFB_KEY` is missing or invalid.
- `.loaf_config.json` contains stale workflow IDs.
- The duplicated workflow was deleted or disabled in KeeperHub.
- The Para wallet lacks Sepolia ETH for gas.
- The wallet lacks Sepolia USDC for job flows that require payment.

Run setup again if workflow IDs are stale:

```bash
loaf-sizzler setup
```

If setup refuses because config already exists, inspect or move the old
`.loaf_config.json` before rerunning setup.

## `get_output` Returns Unauthorized

Common reasons:

- The request did not include `X-From-Peer-Id`.
- The caller AXL key does not match the verifier profile's registered AXL key.
- The verifier is not assigned to the job.
- The wrong `verifier_profile_id` was provided.

The intended request path is through AXL so the caller identity header is set by
the requesting runtime.

## `get_output` Returns `output tampered`

The locally stored output hash does not match the job's on-chain output hash.

Possible causes:

- The output was changed after `submit_work`.
- The local storage belongs to a different runtime instance.
- The job ID points to a different job than expected.

For important flows, prefer SQLite storage and avoid sharing one database across
multiple running instances.

## Unit Tests Do Not Run With Pytest

Symptom:

```text
No module named pytest
```

The unit suite can run without pytest:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Install pytest only if you want that runner locally.

## End-To-End Script Fails Immediately

The e2e script is not hermetic. It needs:

- Runtime A at `LOAF_E2E_BASE_A`.
- Runtime B at `LOAF_E2E_BASE_B`.
- Valid AXL keys.
- Valid profile IDs.
- A valid numeric on-chain job ID.
- Working KeeperHub workflows.

Configure it before running:

```bash
LOAF_E2E_JOB_ID=1 \
LOAF_E2E_PROFILE_A=10 \
LOAF_E2E_PROFILE_B=20 \
python tests/e2e_test.py
```

