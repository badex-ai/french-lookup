"""Ask Claude through the `claude` CLI, which uses the user's subscription login."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from .config import DATA_DIR, Config

_RULES = (
    "Plain text only: no markdown, no asterisks, no bullet symbols, no headings, "
    "and never use the characters < or >. No preamble, no closing remarks."
)

WORD_PROMPT = (
    "You are a French tutor for an English speaker. The user selected one French word. "
    "Answer in exactly these labelled lines, each on its own line:\n"
    "Meaning: the English translation(s)\n"
    "Form: part of speech and base form (infinitive for verbs, masculine singular for nouns "
    "and adjectives), plus tense and person if it is a conjugated verb\n"
    "Example: one very short French sentence (English translation in brackets)\n"
    "Keep every line short. " + _RULES
)

PHRASE_PROMPT = (
    "You are a French tutor for an English speaker. The user selected a French phrase. "
    "Answer in these labelled lines, each on its own line, one idea per line:\n"
    "Meaning: the English translation\n"
    "Rule: the grammar rule or construction that makes the phrase work (tense, mood, "
    "agreement, pronoun placement, idiom, ...)\n"
    "Verbs: the infinitive of every conjugated verb and how it is formed here\n"
    "Why: one sentence on why it takes this form\n"
    "Example: one short extra French sentence using the same rule (English in brackets)\n"
    "Leave out Verbs if there is no verb. Keep every line to one or two short sentences. " + _RULES
)

_STRIP = " \t\n.,;:!?«»\"“”()[]…"


class LookupError_(Exception):
    """A lookup failed; the message is safe to show to the user."""


def normalize(text: str) -> str:
    return " ".join(text.split())


def is_single_word(text: str) -> bool:
    return len(normalize(text).split(" ")) == 1


def clean_selection(text: str) -> str:
    text = normalize(text)
    return text.strip(_STRIP) if is_single_word(text) else text


def find_claude(cfg: Config) -> str:
    for candidate in (cfg.claude_path, shutil.which("claude"), str(Path.home() / ".local/bin/claude")):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise LookupError_("Claude Code isn't installed (no `claude` command found).")


def build_command(claude: str, cfg: Config, text: str) -> list[str]:
    prompt = WORD_PROMPT if is_single_word(text) else PHRASE_PROMPT
    return [
        claude, "-p", text,
        "--model", cfg.model,
        "--effort", "low",
        "--system-prompt", prompt,
        "--output-format", "json",
        "--no-session-persistence",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--tools", "",
    ]


def start(cfg: Config, text: str) -> subprocess.Popen:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        build_command(find_claude(cfg), cfg, text),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=DATA_DIR,
        start_new_session=True,
    )


def wait(proc: subprocess.Popen, cfg: Config) -> str:
    try:
        out, err = proc.communicate(timeout=cfg.timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise LookupError_(f"Claude took longer than {cfg.timeout_seconds} s. Try again.")
    if proc.returncode < 0:
        raise LookupError_("Cancelled.")
    return parse_output(out, err)


def parse_output(out: str, err: str) -> str:
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise LookupError_(_explain_failure(out + "\n" + err))
    result = (data.get("result") or "").strip()
    if data.get("is_error") or not result:
        raise LookupError_(_explain_failure(result or err))
    return sanitize(result)


def sanitize(answer: str) -> str:
    answer = answer.replace("<", "").replace(">", "").replace("**", "")
    lines = [line.strip() for line in answer.splitlines()]
    return "\n".join(line for line in lines if line)


def _explain_failure(message: str) -> str:
    lower = message.lower()
    if "limit" in lower:
        return "Claude usage limit reached. It resets after a while; try again later."
    if "log in" in lower or "login" in lower or "authenticat" in lower:
        return "Claude Code is logged out. Open a terminal, run `claude`, and log in."
    if any(w in lower for w in ("network", "enotfound", "econn", "fetch failed", "connection")):
        return "Couldn't reach Claude. Check your internet connection."
    first_line = next((l for l in message.strip().splitlines() if l.strip()), "unknown error")
    return f"Claude failed: {first_line[:200]}"


def ask(cfg: Config, text: str) -> str:
    return wait(start(cfg, text), cfg)
