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

`skill/anki/` is a **self-contained skill directory** — SKILL.md, the CLI, the MCP
server and the API reference all live inside it, so one directory is the whole
skill.

Two ways to wire it up:

```bash
# (a) Load it straight from a checkout — no installed copy, nothing to drift.
#     In ~/.hermes/config.yaml:
skills:
  external_dirs:
    - ~/code/anki-agent/skill
```

```bash
# (b) Copy it into the profile's skills dir
cp -r skill/anki ~/.hermes/skills/anki
echo 'ANKI_USERID=...' > ~/.hermes/skills/anki/.env
echo 'ANKI_PASSWORD=...' >> ~/.hermes/skills/anki/.env
chmod 600 ~/.hermes/skills/anki/.env
```

Credentials go in a `.env` next to `anki.py` (gitignored). The library also reads
`ANKI_USERID` / `ANKI_PASSWORD` from the environment, if that suits your host better.

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
    args: ["/absolute/path/to/anki-agent/skill/anki/mcp_server.py"]
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
      "args": ["/absolute/path/to/anki-agent/skill/anki/mcp_server.py"],
      "env": {
        "ANKI_USERID": "your_username",
        "ANKI_PASSWORD": "your_password"
      }
    }
  }
}
```

### Standalone CLI

The vendored `anki.py` works as a standalone CLI with no dependencies (it lives
inside the skill directory):

```bash
python3 skill/anki/anki.py list-decks
python3 skill/anki/anki.py create_deck "Spanish::Verbs"
python3 skill/anki/anki.py add_card "hola" "hello" -d "Spanish::Verbs" -n Basic
python3 skill/anki/anki.py search "deck:Spanish front:hola"
python3 skill/anki/anki.py update_card 1780339347382 -f "Front=hola (informal)"
```

## What's in this repo — and what isn't

This repo is the **API layer only**: how to talk to AnkiWeb's `/svc/` endpoints
from any agent or script. It is agent-framework-neutral.

| In here | Not in here |
| --- | --- |
| `skill/anki/anki.py` — vendored CLI + client library | Your credentials (`.env`, gitignored) |
| `skill/anki/mcp_server.py` — FastMCP wrapper, 9 tools | Any particular deck's rules or contents |
| `skill/anki/SKILL.md` + `references/ankiweb-api.md` | Deck-specific tooling (lint/apply scripts, audit logs) |
| Install instructions for Hermes and Claude Desktop | Cron jobs |

Everything a skill needs is inside `skill/anki/`, so a consumer can take that one
directory and have a working skill: the CLI, the MCP server, the instructions and
the API reference travel together and cannot drift apart.

Deck-specific layers live elsewhere by design: the standards for a particular
deck belong with that deck, not with the API client. A deck's tooling only ever
needs `anki.py` from here.

### Portability

- **Portable core:** `anki.py`, `mcp_server.py`, `references/ankiweb-api.md` — pure
  stdlib Python 3.10+, no Hermes dependency. Any MCP host or shell script can use them.
- **Portable-ish:** `SKILL.md` — plain markdown using the generic
  skill convention (`name` + `description` frontmatter, "base directory for this
  skill" placeholder). It reads as an agent-generic skill; the only
  framework-specific parts are the install paths and the MCP registration snippet,
  which are labelled as such in *Setup*.
- **Hermes-specific:** nothing in the library. The Hermes mentions are install
  plumbing only, and Claude Desktop is documented alongside so the skill is not
  tied to one host.

## Keeping it honest

`skill/anki/` is a complete, self-contained skill: it is loaded straight from this
checkout (`skills.external_dirs` in the host's config), so there is no installed
copy that can drift from the repo. Edit here, commit, done — nothing to deploy.

If you do copy it into a profile's skills folder instead, note that a copy *can*
drift, and compare the two rather than trusting them.

Upstream tracking: `anki.py` is vendored from
[`htlin222/ankiweb-add-card`](https://github.com/htlin222/ankiweb-add-card) (MIT).
Track upstream changes and cherry-pick what is useful — the vendored file here has
local modifications, so it is not a drop-in replacement for upstream.

## ⚠️ Disclaimer

This tool talks to AnkiWeb's **private, undocumented endpoints**, which may change at any time without notice. Use only with your own account. Not affiliated with or endorsed by Anki or AnkiWeb.

## License

MIT. The vendored `anki.py` is MIT-licensed, originally from [`htlin222/ankiweb-add-card`](https://github.com/htlin222/ankiweb-add-card).
