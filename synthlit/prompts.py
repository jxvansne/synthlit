"""The exact text a model under test receives. Everything sent to a model goes through here,
so the canary is stripped and the leak scan runs in one place."""
from __future__ import annotations

import hashlib
import os

from .canary import assert_no_canary, strip_canary
from .generate import leak_scan

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
PASTE_MARKER = "[PASTE packet.md BELOW THIS LINE]"
# Sent once, when a model's first reply only asks for information (CLAUDE.md, eval hygiene).
CLARIFICATION_REPLY = "Please treat the summaries as given."
# Sent once, when a model's first reply declines to do the synthesis (wording approved by Jared, 2026-10-29).
PROCEED_REPLY = "Please treat the summaries as given and proceed with the synthesis."


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, f"{name}.md"), encoding="utf-8") as f:
        return strip_canary(f.read())


def stage1_message(packet_md: str) -> str:
    """Stage 1 prompt with the packet pasted in place of the marker, exactly as in the pilot run kits."""
    prompt = load_prompt("stage1")
    packet = strip_canary(packet_md)
    head = prompt[: prompt.index(PASTE_MARKER)].replace("{n_studies}", str(packet.count("**Study ")))
    text = head + packet
    assert_no_canary(text)
    leaks = leak_scan(text)
    if leaks:
        raise ValueError(f"Stage 1 message leaks {leaks}")
    return text


def stage2_message() -> str:
    text = load_prompt("stage2")
    assert_no_canary(text)
    return text


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
