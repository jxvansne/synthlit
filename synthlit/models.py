"""Models under test: how a subject is named, priced and parameterized.

A subject is written MODEL@EFFORT, plus "+code" for the agentic condition
(provider-hosted code execution), e.g. claude-opus-5-5@medium or claude-haiku-5-5@low+code.
"""
from __future__ import annotations

from dataclasses import dataclass

# USD per million tokens (input, output), standard tier. Batch requests cost half.
# Source: Anthropic pricing as cached 2026-10-06; re-check
# https://platform.claude.com/docs/en/about-claude/pricing before any large run.
PRICES = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
PRICES_AS_OF = "2026-10-06"
BATCH_DISCOUNT = 0.5
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Planning guesses for output tokens (thinking + answer) per Stage 1 reply. Replace with
# measured values from runs/*/ once a pilot exists (`harness status` prints them).
OUTPUT_TOKENS_GUESS = {"low": 7000, "medium": 10000, "high": 18000, "xhigh": 30000, "max": 45000}  # Haiku 5.5 low wrote ~6-7k (2026-10-28)
STAGE2_OUTPUT_TOKENS_GUESS = 1500


@dataclass(frozen=True)
class Subject:
    model: str
    effort: str
    agentic: bool = False

    @property
    def provider(self) -> str:
        if self.model.startswith("claude-"):
            return "anthropic"
        if self.model.startswith("fake-"):
            return "fake"
        if self.model.startswith(("gpt-", "o1", "o3", "o4", "o5")):
            return "openai"
        raise ValueError(f"unknown provider for model {self.model}")

    @property
    def slug(self) -> str:
        return f"{self.model}_{self.effort}" + ("_code" if self.agentic else "")

    def __str__(self) -> str:
        return f"{self.model}@{self.effort}" + ("+code" if self.agentic else "")


def parse_subject(spec: str) -> Subject:
    spec = spec.strip()
    agentic = spec.endswith("+code")
    spec = spec.removesuffix("+code")
    if "@" not in spec:
        raise ValueError(f"subject {spec!r} must be MODEL@EFFORT")
    model, effort = spec.split("@", 1)
    if effort not in EFFORTS:
        raise ValueError(f"effort {effort!r} must be one of {EFFORTS}")
    s = Subject(model, effort, agentic)
    if s.provider == "anthropic" and model not in PRICES:
        raise ValueError(f"no price for {model}; add it to PRICES (check the pricing page)")
    return s


def cost_usd(model: str, input_tokens: int, output_tokens: int, batch: bool) -> float:
    if model not in PRICES:
        return 0.0
    pin, pout = PRICES[model]
    c = (input_tokens * pin + output_tokens * pout) / 1e6
    return c * BATCH_DISCOUNT if batch else c
