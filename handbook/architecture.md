# Architecture

`loaf-sizzler` sits between an MCP-capable agent, the AXL network, KeeperHub,
and the Loaf escrow contract.

## Runtime Components

### CLI

Entry point: `loaf_sizzler/cli.py`

The CLI owns runtime startup:

1. Load `.env` from the current directory or one of its parents.
2. Initialize storage with `create_storage()`.
3. Connect to the configured AXL node.
4. Create the KeeperHub-backed contract client.
5. Start the Flask MCP server.
6. Register the service with the configured MCP router.

The main command is:

```bash
loaf-sizzler start
```

The setup command is:

```bash
loaf-sizzler setup
```

### MCP Server

Entry point: `loaf_sizzler/server.py`

The server exposes a JSON-RPC MCP endpoint:

```text
POST /mcp
```

It supports:

- `initialize`
- `notifications/initialized`
- `ping`
- `tools/list`
- `tools/call`

`GET /mcp` intentionally returns `405` because this server does not provide a
server-initiated SSE stream.

Tool calls are dispatched from `MCPServer._call_tool()` into small functions
under `loaf_sizzler/tools/`.

### AXL Client

Entry point: `loaf_sizzler/axl_client.py`

The AXL client sends messages through a local AXL node. It is used for:

- Worker bids.
- Poster acceptances.
- Verifier bids.
- Verifier assignments.
- Settlement/verdict messages.
- Remote output requests.

AXL messages are sent by calling the remote peer's `receive_message` MCP tool
through the local AXL node route:

```text
{AXL_NODE_URL}/mcp/{peer_id}/loaf-sizzler
```

### Contract Client

Entry point: `loaf_sizzler/contract_client.py`

The contract client wraps KeeperHub workflow execution. It is responsible for:

- Loading workflow IDs from `.loaf_config.json`.
- Executing workflow webhooks.
- Polling workflow executions.
- Normalizing job/profile payloads.
- Lazy profile registration before write operations.
- Converting USDC amounts into 6-decimal raw units.

The client does not call an Ethereum RPC endpoint directly. Contract writes and
reads are mediated through KeeperHub workflows.

### Storage

Entry points:

- `loaf_sizzler/storage/memory.py`
- `loaf_sizzler/storage/sqlite.py`
- `loaf_sizzler/storage/base.py`

Storage is used for:

- Incoming AXL inbox messages.
- Worker output stored locally by job ID.
- Local agent metadata such as cached profile ID.

The memory backend is ephemeral and useful for simple local runs. SQLite is the
runtime-safe option when data should survive process restarts.

## Request Flow

### Worker Bid Flow

1. Agent calls `bid_job`.
2. The runtime ensures the worker has a registered profile.
3. The worker's AXL key is read from the local AXL node.
4. A bid message is sent to the poster through AXL.
5. The poster receives the message through `receive_message`.
6. The poster can inspect it with `get_inbox`.

### Poster Accepts Worker

1. Agent calls `accept_bid`.
2. The runtime ensures the poster has a registered profile.
3. The job is loaded so verifier fees can be included in approval.
4. USDC approval is executed through KeeperHub.
5. The accept-bid workflow is executed through KeeperHub.
6. The worker receives an AXL acceptance message.

### Worker Submits Work

1. Agent calls `submit_work`.
2. The runtime hashes the output with SHA-256.
3. The output is stored locally.
4. The output hash is submitted through KeeperHub.

### Verifier Gets Output

1. Verifier calls the worker's `get_output` tool through AXL.
2. The request must include `X-From-Peer-Id`.
3. The runtime loads the verifier profile and checks that the caller AXL key
   matches the profile.
4. The runtime checks the verifier is assigned to the job.
5. The stored output hash is compared with the on-chain hash when available.
6. The output is returned only if authorization and integrity checks pass.

### Verifier Submits Verdict

1. Agent calls `submit_verdict`.
2. The runtime writes the verdict through KeeperHub.
3. The poster receives a settlement message through AXL.

