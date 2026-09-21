---
name: anki
description: >-
  Manage Anki decks and flashcards on the user's AnkiWeb account. Create decks,
  add/edit/search cards, list notetypes. No running Anki desktop or AnkiConnect
  required — talks directly to AnkiWeb's internal API. Use whenever the user
  wants to add a flashcard or note to Anki, create or rename a deck, search
  existing cards, or list their decks. E.g. "add a card to my Spanish deck",
  "make an Anki deck called X", "search my flashcards for Y".
---

# Anki

Create decks and manage flashcards on the user's AnkiWeb account. The bundled
CLI (`anki.py`) logs in with credentials from `.env`, caches the session, and
calls AnkiWeb's internal protobuf endpoints directly. No browser, no Anki
desktop, no AnkiConnect add-on.

## Running the CLI

The skill is installed at a runtime path shown as **"Base directory for this
skill"**. Always invoke the CLI by absolute path:

```bash
SKILL="<the base directory for this skill>"
python3 "$SKILL/anki.py" <command> [args]
```

The CLI is pure Python stdlib — no dependencies, no install step.

Login happens automatically on the first command and is cached; don't run
`login` unless a command fails with an auth error.

`references/ankiweb-api.md` (in this skill's directory) holds the endpoint map,
protobuf wire format, discovery methodology and the full operational-quirk list.
Read it before doing anything unusual with the API, or when adding an endpoint.

## Hard limits

These bite silently, so treat them as constraints, not warnings.

- **Search returns at most 100 rows, whatever the query.** There is no
  offset/limit field and no truncation marker, so a capped result is
  indistinguishable from a complete one. **A single search is never an
  inventory** — never derive a card count, or claim a deck is clean, from one
  `deck:` query. For true contents, partition by the first character of `Front`,
  then by the first character of `Back`, and union the buckets (include accented
  letters, digits and punctuation or those notes are invisible); assert no bucket
  returned exactly 100, since a capped bucket is truncated too. `search
  "nid:<note_id>"` is the cheap existence check for one note.
- **No single-note delete.** `update_card` cannot remove a note and there is no
  `remove-note` call. To clear unwanted notes out of a deck you are keeping, tag
  them (e.g. `dup`) so they can be found and deleted in Anki desktop. Never blank
  a note's fields to "remove" it — that leaves an empty card behind. `remove-deck`
  deletes the whole deck and its cards.
- **`get-note-info` costs about a second per note.** A 200-note dump takes
  minutes: run it as one call with a generous timeout (or in the background with
  a completion notification), never a tight loop of small calls. Cache the dump —
  re-fetching notes you already hold is waste.
- **`rename-deck` to an existing name does not error** — AnkiWeb silently
  appends `+`. Check the deck list first if the target name might collide.
- **Test on a throwaway deck.** With no note-delete, test cards are permanent
  unless the whole deck goes. Create `_tmp_test`, test, then
  `remove-deck _tmp_test`. Never add test cards to a real deck.
- **Edits have no undo.** `update_card` overwrites the previous revision and there
  is no way to fetch it back. For bulk work, write intended changes to an ops file
  and validate every proposed value against the rule set before applying, print
  without writing first, then apply one call per note while appending before/after
  values to a log so every edit stays reversible.

## Commands

```bash
# Create a deck ('::' nests subdecks; missing parent levels auto-created)
python3 "$SKILL/anki.py" create_deck "Spanish::Verbs"

# Add a card — positional values fill fields IN ORDER (Front, Back for Basic)
python3 "$SKILL/anki.py" add_card "hola" "hello" -d "Spanish::Verbs" -n Basic

# Override a field by name, attach tags
python3 "$SKILL/anki.py" add_card "Q" "A" -f "Extra=a note" -t "tag1 tag2"

# Omit -d/-n to use the user's last-used deck and note type
python3 "$SKILL/anki.py" add_card "front" "back"

# Search for notes -> 'note_id<TAB>field-summary'
python3 "$SKILL/anki.py" search "deck:Spanish front:hola"

# Edit a card in place by note id (from search, or the /edit/<id> URL)
python3 "$SKILL/anki.py" update_card 1780339347382 -f "Front=hola (informal)"

# List decks / note types (id<TAB>name)
python3 "$SKILL/anki.py" list-decks
python3 "$SKILL/anki.py" list-notetypes

# Rename a deck ('::' moves it under a parent)
python3 "$SKILL/anki.py" rename-deck "Spanish" "Español"

# Remove a deck AND its cards (parent removal also removes subdecks)
python3 "$SKILL/anki.py" remove-deck "Spanish::Verbs"
```

### `add_card` flags

| Flag | Meaning |
| --- | --- |
| positional `values...` | field values in the note type's field order (commonly Front, Back) |
| `-d, --deck` | deck name (resolved to id) or numeric id; default: last used |
| `-n, --notetype` | note type name or numeric id; default: last used |
| `-f, --field NAME=VALUE` | set a field by name; repeatable; overrides positional |
| `-t, --tags` | space-separated tags |

### Editing an existing card (`search` + `update_card`)

There is no "edit by content" — you edit by **note id**, which you get from
`search` (or from the AnkiWeb editor URL `ankiuser.net/edit/<note_id>`).

1. `search "<query>"` — Anki search syntax (`deck:X`, `front:Y`, `tag:Z`, or
   free text). Prints `note_id<TAB>summary`.
2. `update_card <note_id> …` — edits that note **in place** (same note id, no
   duplicate created). Omitted fields keep their current value; tags persist
   unless `-t` is given.

| `update_card` flag | Meaning |
| --- | --- |
| positional `note_id` | required; numeric id from `search` |
| positional `values...` | new field values in order; **omitted trailing positions keep current value** |
| `-f, --field NAME=VALUE` | set one field by name; repeatable — **preferred for single-field edits** |
| `-t, --tags` | replace tags; **omit to keep the note's existing tags** |

Safety notes:

- Editing only ever touches the one note you name; unspecified fields and (when
  `-t` is omitted) tags are read back and preserved.
- AnkiWeb has **no single-note delete** — `update_card` cannot remove a note.
  To delete, you must `remove-deck` the whole deck.

## Card design — default to *short question / short answer / context below*

Unless the user asks for a different format, author cards in this shape:

- **Front = one focused question.** A single, irreducible concept.
- **Back, line 1 = the short answer.** Minimal correct response.
- **Back, below an `<hr>` = the context.** Explanation, mnemonic, source.

```bash
python3 "$SKILL/anki.py" add_card \
  "What does a positive Murphy's sign indicate?" \
  "Acute cholecystitis<hr>Inspiratory arrest on RUQ palpation due to an inflamed gallbladder."
```

Rules of thumb:

- Err toward more, smaller cards, but use the context block to prevent
  over-atomization.
- For lists/enumerations, use a **Cloze** note type with one deletion per item.
- HTML is allowed in field values (`<b>`, `<br>`, `<hr>`, etc.).

## Usage notes

- **Resolve names, don't guess ids.** Deck and note type arguments accept the
  human name; the CLI resolves it. Run `list-decks` / `list-notetypes` first if
  unsure.
- An unknown name returns a "Did you mean …?" hint — surface it to the user.
- `rename-deck` to a name that already exists does not error — AnkiWeb silently
  appends `+`. Check `list-decks` if the target name might collide.
- The CLI writes to the user's real account. Confirm ambiguous mutations before
  running them.
