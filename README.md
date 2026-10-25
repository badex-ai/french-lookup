# french-lookup

Select French text in any app, press **Super+F**, and a popup explains it:

- one word (double-click it): translation, base form, tense
- a phrase (drag over it): the grammar rule behind it, with an extra example

Press **Enter** to save the lookup as a flashcard, **Esc** to close without saving.

Answers come from Claude through the Claude Code CLI (`claude -p`), so it uses your
Claude subscription login. No API key needed.

## Requirements

- Ubuntu/GNOME on an **X11** session
- [Claude Code](https://claude.com/claude-code) installed and logged in
- For the tray icon: `sudo apt install gir1.2-ayatanaappindicator3-0.1`

## Install / uninstall

```sh
./install.sh            # copies to ~/.local/lib, binds Super+F, starts at login
./uninstall.sh          # removes everything except your cards
./uninstall.sh --purge  # also deletes cards and config
```

## Flashcards (Brainscape)

Saved cards go into batches of 200 in `~/.local/share/french-lookup/batches/`
(`batch-001.csv`, `batch-002.csv`, ...): two columns (question, answer), no header,
which is the format Brainscape imports. When a batch is full, the next card starts
a new one.

1. Upload the oldest batch on brainscape.com (Create → Import).
2. Tray icon → **Mark batch-00N.csv as uploaded**. It moves to `uploaded/`.

You can upload a batch before it's full. Numbers are never reused, and a word or
phrase is only ever saved once.

## Config

Optional `~/.config/french-lookup/config.toml`:

```toml
model = "sonnet"       # or "haiku", "opus"
timeout_seconds = 30
max_chars = 300
batch_size = 200     # cards per CSV
```

## Development

```sh
python3 -m unittest                             # tests
python3 -m french_lookup ask "j'ai perdu"       # one lookup in the terminal
```
