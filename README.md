# anki-agent

Anki skill and MCP server for AI agents. Manage Anki decks and flashcards on AnkiWeb **without a running Anki desktop instance or AnkiConnect add-on** — talks directly to AnkiWeb's internal protobuf `/svc/` API.

Two integrations included:

1. **MCP server** — exposes deck/card operations as MCP tools for any MCP-compatible agent (Hermes, Claude Desktop, etc.)
2. **Hermes/Agent skill** — a drop-in `SKILL.md` + CLI for agents that use the skill convention

## What it can do

| Operation | MCP tool / CLI command |
| --- | --- |
| List decks | `list_decks` / `list-decks` |
| Create deck (supports `::` nesting) | `create_deck` / `create_deck` |
| Rename / move deck | `rename_deck` / `rename-deck` |
| Remove deck (and its cards) | `remove_deck` / `remove-deck` |
| Add card (note) | `add_card` / `add_card` |
| Edit existing card in place | `update_card` / `update_card` |
| Search notes (Anki search syntax) | `search_notes` / `search` |
| Get note details | `get_note_info` / *(internal)* |
| List note types | `list_notetypes` / `list-notetypes` |

## How it works

AnkiWeb's web app talks to internal protobuf-based `/svc/` endpoints on `ankiweb.net` and `ankiuser.net`. The vendored `anki.py` reverse-engineers these endpoints to create decks, add/edit/search cards, and manage note types — all without a browser or a local Anki install.

The CLI logs in once with your credentials, caches both domain session cookies, and speaks the same wire protocol the AnkiWeb web app uses.

### Vendored library

`anki.py` is vendored from [`htlin222/ankiweb-add-card`](https://github.com/htlin222/ankiweb-add-card) (MIT license). It's a zero-dependency, pure-stdlib Python 3.10+ file. We vendor rather than pip-install because:

- The whole design philosophy is "no install step" — `python3 anki.py` runs anywhere
- These are undocumented, unofficial endpoints that may break without notice; vendoring lets us patch immediately
- The file is 542 lines with no third-party deps — minimal maintenance overhead

Track upstream changes and cherry-pick as needed.

## Setup

### Credentials

The library checks for credentials in this order:

1. **Environment variables** `ANKI_USERID` and `ANKI_PASSWORD` (used by MCP server)
2. **`.env` file** next to `anki.py` (used by skill / standalone CLI)

You can use either or both. The simplest approach: create a `.env` file, which works for all three integrations (the MCP server also reads it as a fallback).

```bash
ANKI_USERID=your_ankiweb_username
ANKI_PASSWORD=your_ankiweb_password
```

### As a Hermes Agent skill

Copy or symlink the `skill/anki/` directory into your skills directory:

```bash
# Example for Hermes Agent (~/.hermes/skills/)
cp -r skill/anki ~/.hermes/skills/anki
cp anki.py ~/.hermes/skills/anki/anki.py
# Add credentials
echo 'ANKI_USERID=...' > ~/.hermes/skills/anki/.env
echo 'ANKI_PASSWORD=...' >> ~/.hermes/skills/anki/.env
chmod 600 ~/.hermes/skills/anki/.env
```

Restart Hermes. The skill is now available.

### As an MCP server

**Install the MCP SDK** (if not already installed):

```bash
pip install mcp
```

**Register in Hermes** (`~/.hermes/config.yaml`):

```yaml
mcp_servers:
  anki:
    command: "python3"
    args: ["/absolute/path/to/anki-agent/mcp_server.py"]
    env:
      ANKI_USERID: "your_username"
      ANKI_PASSWORD: "your_password"
```

Restart Hermes. Tools will appear prefixed with `mcp_anki_` (e.g. `mcp_anki_list_decks`, `mcp_anki_add_card`).

**Register in Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "anki": {
      "command": "python3",
      "args": ["/absolute/path/to/anki-agent/mcp_server.py"],
      "env": {
        "ANKI_USERID": "your_username",
        "ANKI_PASSWORD": "your_password"
      }
    }
  }
}
```

### Standalone CLI

The vendored `anki.py` works as a standalone CLI with no dependencies:

```bash
python3 anki.py list-decks
python3 anki.py create_deck "Spanish::Verbs"
python3 anki.py add_card "hola" "hello" -d "Spanish::Verbs" -n Basic
python3 anki.py search "deck:Spanish front:hola"
python3 anki.py update_card 1780339347382 -f "Front=hola (informal)"
```

## ⚠️ Disclaimer

This tool talks to AnkiWeb's **private, undocumented endpoints**, which may change at any time without notice. Use only with your own account. Not affiliated with or endorsed by Anki or AnkiWeb.

## License

MIT. The vendored `anki.py` is MIT-licensed, originally from [`htlin222/ankiweb-add-card`](https://github.com/htlin222/ankiweb-add-card).
