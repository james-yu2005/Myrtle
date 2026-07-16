# Notion Notes MCP for Desk Chat

Lets Desk Chat create and update notes in Notion through Notion's official
hosted MCP server.

```
You → Desk Chat → xiaozhi.me → this bridge → Notion MCP → Desk Chat Notes
```

## Restrict access to one page

1. In Notion, create a page named **Desk Chat Notes**.
2. On the first bridge launch, Notion opens an OAuth page picker.
3. Choose **Select pages** and select only **Desk Chat Notes**.
4. Do not select the workspace root or a parent containing other private pages.

Notion enforces the selected-page permission. The prompt and tool descriptions
are not the security boundary.

## Setup

```bash
cd scripts/mcp_notion
cp .env.example .env
```

Copy the same xiaozhi MCP endpoint used by your other bridges into `.env`, then:

```bash
chmod +x start.sh
./start.sh
```

If `scripts/mcp_search/.env` exists, `start.sh` can reuse its `MCP_ENDPOINT`, so
creating a second `.env` is optional.

The first run opens a browser for Notion OAuth. Sign in, choose **Select pages**,
and grant access only to **Desk Chat Notes**.

After authorization, try:

- “Add ‘order replacement filters’ to my Desk Chat Notes page.”
- “Jot down that my Tavily MCP setup is working.”
- “Read my latest Desk Chat notes.”

Be explicit about the **Desk Chat Notes** page so the model selects the right
destination.

## Will a browser open every time?

No. `mcp-remote` stores OAuth credentials in this folder's `.mcp-auth/`
directory and refreshes them. A browser is normally needed only for initial
authorization, after revocation, after roughly 180 days, or after 30 days of
inactivity. Keep `.mcp-auth/` private and persistent.

## Running in the cloud

Tavily and Notion can run on an always-on host if you persist `.env` and
`.mcp-auth/`. Tapo must stay on the home LAN. See
[mcp-cloud-integrations.md](../../docs/mcp-cloud-integrations.md).

## Files

| File | Purpose |
|------|---------|
| `mcp_config.json` | Official Notion MCP via `mcp-remote` |
| `mcp_pipe.py` | stdio ↔ xiaozhi WebSocket |
| `start.sh` | Creates a virtualenv and starts the bridge |
| `.env` | xiaozhi endpoint token (gitignored) |
| `.mcp-auth/` | Notion OAuth credentials (gitignored) |
