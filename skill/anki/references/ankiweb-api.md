# AnkiWeb Protobuf `/svc/` API Reference

AnkiWeb's web interface talks to internal protobuf-based `/svc/` endpoints.
These are undocumented and unofficial — reverse-engineered from the web app's
network traffic and compiled SvelteKit JS bundle. AnkiWeb can change them at any
time; use only with an account you own.

Everything in this file is framework-neutral API knowledge. It belongs with the
code in this repo, not with any particular agent's skill tree.

## Why talk to `/svc/` directly

**AnkiWeb has no official public API** — the creator has declined to build one.
All automation falls into one of three approaches:

| Approach | Requires Anki running? | Automated sync? |
|----------|----------------------|-----------------|
| AnkiConnect (local HTTP API to the desktop app) | Yes | Yes |
| `genanki` (offline `.apkg` generation) | No | No — manual import |
| **Direct AnkiWeb protobuf `/svc/`** (this library) | **No** | **Yes** |

Direct `/svc/` is the only one of the three that works from a headless machine
with no Anki install *and* writes straight to the account. That is the whole
reason this library exists: a server or agent can create and edit cards, and the
user syncs them down to laptop and phone through normal Anki sync.

## Two access paths, same backend

`mcp_server.py` wraps `AnkiWebClient` as MCP tools; `anki.py` exposes the same
operations as a CLI. Same library, same credentials, two invocation styles:

- **MCP tools** — structured calls, lower token cost, and they work on surfaces
  with no terminal.
- **CLI + skill** — costs more per call (the agent reads the skill and builds a
  shell command) but carries the card-design guidance that shapes *how* cards
  should be written. The MCP tools only know how to add a card, not what a good
  one looks like.

Both can coexist. They share one `.env`.

## Two-domain split

AnkiWeb splits its API across two domains, each with its own session cookie
(same login, different `c` claim):

| Operation | Host | Cookie |
|-----------|------|--------|
| add/update/list cards & notetypes, get-note-info, search | `ankiuser.net` | `c:2` |
| create/rename/list/remove decks, search | `ankiweb.net` | `c:1` |

A single login obtains both cookies:

1. `POST ankiweb.net/svc/account/login` `{username, password}` → `ankiweb.net`
   cookie + an `ankiuser-login` token
2. `GET ankiuser.net/account/ankiuser-login?t=…` → `ankiuser.net` cookie

A 403 on either domain triggers auto-relogin; only the expired domain's session
is re-established.

## Mapped endpoints

### `/svc/account/login` (ankiweb.net)

- **Request:** `{1: username (string), 2: password (string)}`
- **Response:** `{1: status (int: 1=OK, 2=BAD_USER, 3=BAD_PASS), 2: token (string)}`

### `/svc/editor/get-info-for-adding` (ankiuser.net)

- **Request:** empty body
- **Response:** `{1: [notetype msgs {1: id, 2: name}], 2: [deck msgs {1: id, 2: name}], 3: current_deck_id, 4: current_notetype_id, 5: [current_fields {2: name}]}`

### `/svc/editor/get-notetype-fields` (ankiuser.net)

- **Request:** `{1: notetype_id (int)}`
- **Response:** `{1: [field msgs {2: name}]}`

### `/svc/editor/add-or-update` (ankiuser.net)

This is a `oneof mode` — it both adds and edits.

- **Request:** `{1: [field values (repeated string)], 2: tags (string), 3: {1: notetype_id, 2: deck_id} (add mode) | 4: {1: note_id} (edit mode)}`
- **Add mode (field 3):** creates a new note
- **Edit mode (field 4):** replaces existing note's fields. Must pre-read current
  values via `get-note-info` to preserve unspecified fields. There is no
  per-field patch — the client re-reads the note, splices the changed fields,
  and writes the whole set back.

### `/svc/editor/get-note-info` (ankiuser.net)

- **Request:** `{1: note_id (int)}`
- **Response:** `{1: [current values (bytes)], 2: [field msgs {2: name}], 3: tags (string)}`

### `/svc/search/search` (ankiweb.net)

- **Request:** `{1: query (string)}`
- **Response:** `{1: [result msgs {1: note_id, 2: field-summary (string)}]}`
- Query uses Anki search syntax: `deck:X`, `front:Y`, `tag:Z`, `nid:<id>`,
  wildcards (`front:a*`), `is:new`, `added:N`, free text.

**Hard cap: 100 results per query, with no offset/limit field.** See
"Operational quirks" below — this is the single most dangerous property of the
API.

### `/svc/decks/create-deck` (ankiweb.net)

- **Request:** `{1: deck_name (string)}` — use `::` to nest
- **Response:** empty (resolve new ID by name from deck list)

### `/svc/decks/rename-deck` (ankiweb.net)

- **Request:** `{1: deck_id (int), 2: new_name (string)}`
- **Response:** `{1: error (string)}` — non-empty means failure
- `::` in new_name moves under a parent (auto-created)

### `/svc/decks/remove-deck` (ankiweb.net)

- **Request:** `{1: deck_id (int)}`
- Response details not fully mapped. Removes the deck **and its cards**; removing
  a parent deck also removes its subdecks.

## Unmapped / potential endpoints

These likely exist (the AnkiWeb web UI supports these actions) but have not been
reverse-engineered yet:

- **Delete single note** — still unmapped after repeated attempts. The upstream
  repo's own note that no endpoint exists matches observation; do not spend time
  hunting for one. Workaround: tag the notes for deletion and have the user
  remove them in Anki desktop (one `tag:<name>` search), or use `remove-deck`
  when the whole deck is disposable.
- **Deck card counts / due counts** — the deck browser shows these; the payload
  likely contains richer fields than currently decoded.
- **Review/answer cards** — scheduling endpoints (answer ease, get due cards).
- **Export deck** — the web UI has an export action.
- **Media upload** — for images/audio in card fields.

## Operational quirks (learned the hard way)

- **A single search is never an inventory.** The 100-row cap is silent — the
  response carries no total and no truncation marker, so a truncated result set
  is indistinguishable from a complete one. Any count derived from one `deck:X`
  query is wrong, and any "the deck is clean" claim built on it is unfounded.
  Partition by first character of `Front`, then independently by first character
  of `Back`, and union the results — include accented letters, digits and
  punctuation in the character set, or a note whose field starts with an
  unlisted character is invisible. Assert **no bucket returned exactly 100** (a
  bucket at the cap is itself truncated and needs splitting). Then prove
  completeness one-directionally: probe `front:<char>*` across a wide character
  set and assert every returned id is already in the collected set — a capped
  bucket can only under-report, so an out-of-set hit proves a gap while a clean
  probe is strong evidence of none.
- **No single-note delete.** Only `remove-deck`. To get unwanted notes out of a
  deck you are keeping, tag them and delete them in Anki desktop. Never blank a
  note's fields to "remove" it — that leaves an empty card in the collection.
- **`get-note-info` costs ~1s per note.** A 200-note dump takes minutes. Run it
  as one long-lived foreground call with a generous timeout (or background with a
  completion notification) — never a tight loop of small calls, which dies
  part-way and leaves no record of where it stopped. Cache the dump to JSON;
  re-fetching notes you already hold is waste.
- **`rename-deck` to an existing name does not error** — AnkiWeb silently
  appends `+`. Check the deck list first if a name collision is possible.
- **Test on throwaway decks.** With no note-delete, test cards persist forever
  unless the whole deck goes. Create `_tmp_test`, test, then `remove-deck
  _tmp_test`. Never add test cards to a real deck.
- **Bulk edits: generate ops, validate, dry-run, apply, log.** Write intended
  changes into a JSON ops file and assert every proposed value against the rule
  set before applying — zero issues is the gate. That one pass catches whole
  error categories instead of surfacing them one note at a time. Then print
  without writing, apply one call per note, and append before/after values to a
  changes log as you go: an edit overwrites the previous revision and there is no
  way to fetch it back.
- **Keep a declared-values file honest.** When bulk edits are driven by a
  checked-in mapping of intended values, a note later corrected by any other
  route keeps its old intended value there and the next generator run re-applies
  it, undoing the correction. Idempotence does not save you — a stale entry still
  emits a diff, just the wrong one. After every hand-fix, update the mapping and
  re-run the generator, asserting it emits an empty op list against live state.
- **Read the source, not the README.** Upstream READMEs for these clients go
  stale fast — the vendored file here advertised fewer features than it
  implemented. Check the code when evaluating a client.
- **Credentials.** Env vars `ANKI_USERID` / `ANKI_PASSWORD` are checked first,
  then a `.env` file next to `anki.py`. Session cookies are cached to the OS temp
  dir (`anki_session.json`, mode 600). An MCP subprocess inherits a filtered
  environment, so the `.env` fallback is what makes a single credential file work
  for both the CLI and the MCP server.

## Protobuf wire format primer

The CLI hand-rolls only the wire types AnkiWeb uses:

| Wire type | Meaning | Encoding |
|-----------|---------|----------|
| 0 | Varint | `(field << 3) \| 0` + varint value |
| 2 | Length-delimited | `(field << 3) \| 2` + length varint + bytes |

Each field is a tag byte (`field_number << 3 | wire_type`) followed by the
value. Varints use 7 bits per byte with the high bit as continuation flag.

Encoding helpers in `anki.py`:

- `pb_string(field, s)` — string field (wire type 2)
- `pb_int(field, n)` — varint field (wire type 0)
- `pb_message(field, payload)` — nested message (wire type 2, length-prefixed)
- `pb_decode(data)` → `{field_no: [values]}`

## Endpoint discovery methodology

To map a new endpoint:

1. **Browser DevTools capture (preferred):** open AnkiWeb in a browser with the
   DevTools Network tab open. Perform the target action (e.g. delete a note).
   Filter for `/svc/` requests. Note the domain, path, request body (view as
   hex/binary), and response body.

2. **Decode the protobuf:** paste the raw bytes into a protobuf decoder (e.g.
   `protoc --decode_raw`). Map field numbers to their meaning by correlating with
   what the UI sent and expected.

3. **Verify against the JS bundle (optional):** AnkiWeb's frontend is compiled
   SvelteKit. Search the bundle for `/svc/` path strings to find endpoint
   definitions and field usage patterns.

4. **Implement in `anki.py`:** follow the existing pattern — add a method to
   `AnkiWebClient`, then a CLI subcommand in `build_parser()` + `main()`.

5. **Test on a throwaway deck:** create `_tmp_test`, exercise the new endpoint,
   clean up with `remove-deck _tmp_test`.

Step 1 is the one thing an agent cannot do alone — it needs a real browser
session and a real account. Everything after that is mechanical.
