"""The exact text a model under test receives. Everything sent to a model goes through here,
so the canary is stripped and the leak scan runs in one place."""
from __future__ import annotations

import hashlib
import os

from .canary import assert_no_canary, strip_canary
from .generate import leak_scan

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
PASTE_MARKER = "[PASTE packet.md BELOW THIS LINE]"
CLARIFICATION_REPLY = "Please treat the summaries as given."


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, f"{name}.md"), encoding="utf-8") as f:
        return strip_canary(f.read())


def stage1_message(packet_md: str) -> str:
    """Stage 1 prompt with the packet pasted in place of the marker, exactly as in the pilot run kits."""
    prompt = load_prompt("stage1")
    head = prompt[: prompt.index(PASTE_MARKER)]
    text = head + strip_canary(packet_md)
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
