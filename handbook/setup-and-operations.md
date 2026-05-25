# Setup And Operations

This page covers runtime setup and operational expectations.

## Required Environment

Create a `.env` file in the project directory or one of its parents:

```bash
KEEPERHUB_API_KEY=kh_...
KEEPERHUB_WFB_KEY=wfb_...
CONTRACT_ADDRESS=0x8De32D82714153E5a0f07Cc10924A677C6dD4b5A
AXL_NODE_URL=http://localhost:9002
MCP_ROUTER_URL=http://localhost:9003
```

Required at startup:

- `KEEPERHUB_API_KEY`
- `CONTRACT_ADDRESS`
- `AXL_NODE_URL`
- `MCP_ROUTER_URL`

Required when executing KeeperHub workflow webhooks:

- `KEEPERHUB_WFB_KEY`

## First-Time Setup

Run:

```bash
loaf-sizzler setup
```

Setup validates the KeeperHub API key, finds the Para wallet, duplicates Loaf
workflows into the user's KeeperHub organization, enables webhook triggers, and
writes `.loaf_config.json`.

The runtime will not start successfully until `.loaf_config.json` exists.

## Starting The Runtime

Default startup:

```bash
loaf-sizzler start
```

Custom port and AXL node:

```bash
loaf-sizzler start --port 7101 --axl-url http://localhost:9012
```

SQLite persistence:

```bash
loaf-sizzler start --storage sqlite --db-path loaf.db
```

The MCP endpoint is:

```text
http://localhost:{port}/mcp
```

## Running Multiple Instances

Use separate ports and separate AXL nodes:

```bash
loaf-sizzler start --port 7100 --axl-url http://localhost:9002 --storage sqlite --db-path poster.db
loaf-sizzler start --port 7101 --axl-url http://localhost:9012 --storage sqlite --db-path worker.db
```

Each instance should use its own storage file. Sharing one SQLite file across
multiple runtime processes is not a supported operating model.

## Storage Backends

### Memory

Use memory storage for short local sessions:

```bash
loaf-sizzler start --storage memory
```

Data is lost on process restart.

### SQLite

Use SQLite for persistent runtime state:

```bash
loaf-sizzler start --storage sqlite --db-path loaf.db
```

SQLite stores:

- Inbox messages.
- Submitted output and output hashes.
- Agent metadata.

## Service Registration

On startup, the CLI attempts to register with the MCP router:

```text
POST {MCP_ROUTER_URL}/register
```

Registration failure is logged as a warning. It does not stop the runtime.

On shutdown, the CLI attempts to deregister:

```text
DELETE {MCP_ROUTER_URL}/register/loaf-sizzler
```

## Security Notes

- Do not expose the Flask development server directly to the public internet.
- Keep `.env` and `.loaf_config.json` out of public artifacts.
- `get_output` relies on the `X-From-Peer-Id` request header and the verifier
  profile's registered AXL key. Preserve that header when proxying AXL traffic.
- Use SQLite for flows where output must remain available after restart.

