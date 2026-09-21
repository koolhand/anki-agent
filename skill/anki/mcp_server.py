#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "mcp>=1.0.0",
# ]
# ///
"""MCP server exposing AnkiWeb deck/card management as tools.

Wraps the vendored AnkiWebClient (anki.py) as MCP tools so any MCP-compatible
agent (Hermes, Claude Desktop, etc.) can manage Anki decks and cards without a
running Anki desktop instance or AnkiConnect.

Run standalone for stdio transport:
    python3 mcp_server.py

Credentials are read from ANKI_USERID and ANKI_PASSWORD environment variables,
or from a .env file next to anki.py.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Import the vendored AnkiWeb client
sys.path.insert(0, str(Path(__file__).resolve().parent))
from anki import AnkiWebClient, AnkiError  # noqa: E402

# ---------------------------------------------------------------------------
# Client management — single shared instance, lazy login
# ---------------------------------------------------------------------------
_client: AnkiWebClient | None = None


def _get_client() -> AnkiWebClient:
    global _client
    if _client is None:
        _client = AnkiWebClient()
    return _client


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("anki-agent")


# -- Decks ------------------------------------------------------------------
@mcp.tool()
def list_decks() -> str:
    """List all Anki decks. Returns 'id<TAB>name' per line."""
    client = _get_client()
    rows = client.get_info_for_adding()["decks"]
    return "\n".join(f"{did}\t{name}" for did, name in rows) or "(no decks)"


@mcp.tool()
def create_deck(name: str) -> str:
    """Create a new deck. Use '::' to create a subdeck (e.g. 'Languages::Spanish').

    Args:
        name: Deck name. Parent decks in a '::' path are auto-created.
    """
    client = _get_client()
    did = client.create_deck(name)
    return f"Created deck '{name}' (id {did})" if did else f"Created deck '{name}' (id not resolved)"


@mcp.tool()
def rename_deck(deck: str, new_name: str) -> str:
    """Rename a deck or move it under a different parent.

    Args:
        deck: Current deck name or numeric id.
        new_name: New name. A '::' moves it under a parent (auto-created).
    """
    client = _get_client()
    res = client.rename_deck(deck, new_name)
    return f"Renamed deck {res['deck_id']} -> '{res['new_name']}'"


@mcp.tool()
def remove_deck(deck: str) -> str:
    """Remove a deck AND ALL its cards. Removing a parent also removes subdecks.

    Args:
        deck: Deck name or numeric id.
    """
    client = _get_client()
    did = client.remove_deck(deck)
    return f"Removed deck {did} ('{deck}')"


# -- Notes / Cards ----------------------------------------------------------
@mcp.tool()
def add_card(
    values: list[str] | None = None,
    deck: str | None = None,
    notetype: str | None = None,
    named_fields: dict[str, str] | None = None,
    tags: str = "",
) -> str:
    """Add a note (flashcard) to a deck.

    Args:
        values: Field values in the notetype's field order (e.g. ["front", "back"]).
        deck: Deck name or id. Omit to use the user's last-used deck.
        notetype: Note type name or id (e.g. "Basic"). Omit for last-used.
        named_fields: Set specific fields by name, e.g. {"Front": "hola"}. Overrides positional values.
        tags: Space-separated tags, e.g. "vocab verb".
    """
    client = _get_client()
    res = client.add_card(
        deck=deck,
        notetype=notetype,
        values=tuple(values or ()),
        named=named_fields,
        tags=tags,
    )
    lines = [
        f"Added card -> deck {res['deck_id']}, notetype {res['notetype_id']}"
        + (f", tags '{res['tags']}'" if res["tags"] else "")
    ]
    for k, v in res["fields"].items():
        lines.append(f"  {k}: {v!r}")
    return "\n".join(lines)


@mcp.tool()
def update_card(
    note_id: int,
    values: list[str] | None = None,
    named_fields: dict[str, str] | None = None,
    tags: str | None = None,
) -> str:
    """Edit an existing note in place (no duplicate created).

    Unspecified fields keep their current value. Tags are preserved unless `tags` is given.

    Args:
        note_id: Numeric note id (from search or the AnkiWeb editor URL).
        values: New field values in order. Omitted trailing positions keep current value.
        named_fields: Set specific fields by name. Preferred for single-field edits.
        tags: Replace tags. Omit to keep the note's existing tags.
    """
    client = _get_client()
    res = client.update_card(
        note_id=note_id,
        values=tuple(values or ()),
        named=named_fields,
        tags=tags,
    )
    lines = [f"Updated note {res['note_id']}" + (f", tags '{res['tags']}'" if res["tags"] else "")]
    for k, v in res["fields"].items():
        lines.append(f"  {k}: {v!r}")
    return "\n".join(lines)


@mcp.tool()
def search_notes(query: str) -> str:
    """Search for notes using Anki's search syntax.

    Args:
        query: Anki search query, e.g. 'deck:Spanish', 'front:hola', 'tag:verb', or free text.
    """
    client = _get_client()
    rows = client.search(query)
    if not rows:
        return "(no matches)"
    return "\n".join(f"{nid}\t{summary}" for nid, summary in rows)


@mcp.tool()
def get_note_info(note_id: int) -> str:
    """Get field names, current values, and tags for a specific note.

    Args:
        note_id: Numeric note id.
    """
    client = _get_client()
    info = client.get_note_info(note_id)
    lines = [f"Note {note_id}:"]
    for name, val in zip(info["fields"], info["values"]):
        lines.append(f"  {name}: {val!r}")
    lines.append(f"  tags: {info['tags']}")
    return "\n".join(lines)


@mcp.tool()
def list_notetypes() -> str:
    """List all note types. Returns 'id<TAB>name' per line."""
    client = _get_client()
    rows = client.get_info_for_adding()["notetypes"]
    return "\n".join(f"{nid}\t{name}" for nid, name in rows) or "(no notetypes)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
