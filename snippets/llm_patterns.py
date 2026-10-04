"""
llm_patterns.py — deterministic linter for LLM-signature prose patterns.

Catches ten families of patterns that LLMs post-RLHF produce at a density
higher than human technical writing. Three families have a frequency cap
(violation above the cap, not on single occurrence). Four families are
prohibited outright (any occurrence is a violation). The remaining three
families are left to the LLM-based style critic because their variants are
too subtle for regex without producing false positives.

The thresholds below are the production values at the author's blog pipeline.
They were tuned against three real articles produced by the Writer agent
plus a small corpus of hand-written reference material.

Returns a list of Violation records. Each record has the pattern family,
the matched span (line number + the matching text), and the rule severity.
"""

import re
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    OVER_CAP = "over_cap"
    PROHIBITED = "prohibited"


@dataclass
class Violation:
    family: str
    severity: Severity
    line: int
    span: str
    count: int | None = None


# K1 contrastive: "no X, sino Y" / "No es X. Es Y." / "The difference is not"
K1_PATTERNS = [
    re.compile(r"\bno\s+\w+(?:\s+\w+){0,3},\s+sino\b", re.IGNORECASE),
    re.compile(r"\bno es\s+[^.]{3,40}\.\s+es\b", re.IGNORECASE),
    re.compile(r"\bthe difference is not\b", re.IGNORECASE),
    re.compile(r"\bwhat separates\s+\w+\s+from\s+\w+\b", re.IGNORECASE),
]
K1_CAP = 1


# K3 triple symmetric enumeration: "X, Y, and Z" that is three parallel items
# of the same syntactic shape (noun-noun-noun or adj-adj-adj). This regex is
# conservative; it only flags obvious triples with the Oxford comma.
K3_PATTERN = re.compile(
    r"\b(\w+ \w+),\s+(\w+ \w+),\s+and\s+(\w+ \w+)\b"
)
K3_CAP = 2


# K6 hedging chain: multiple hedges in a short window.
K6_HEDGES = {"typically", "generally", "usually", "often", "arguably", "likely", "perhaps"}
K6_CAP = 2  # per document


# K4 artificial deepening: in essence, fundamentally, at the core
K4_PATTERNS = [
    re.compile(r"\bin essence\b", re.IGNORECASE),
    re.compile(r"\bfundamentally\b", re.IGNORECASE),
    re.compile(r"\bat the core\b", re.IGNORECASE),
    re.compile(r"\bevidently\b", re.IGNORECASE),
    re.compile(r"\bclearly\b", re.IGNORECASE),
]


# K5 meta-commentary openers
K5_PATTERNS = [
    re.compile(r"^\s*this (article|section|post)\s+(argues|shows|explains|demonstrates|covers)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*in this (article|section|post|document)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*below we\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*the rest of this\b", re.IGNORECASE | re.MULTILINE),
]


# K7 generic bridges
K7_PATTERNS = [
    re.compile(r"\bas we saw\b", re.IGNORECASE),
    re.compile(r"\bas mentioned above\b", re.IGNORECASE),
    re.compile(r"\bas discussed\b", re.IGNORECASE),
    re.compile(r"\bas shown earlier\b", re.IGNORECASE),
]


# K8 weak periphrases: "Lo que hace que X sea Y"
K8_PATTERNS = [
    re.compile(r"\blo que hace que\b", re.IGNORECASE),
    re.compile(r"\bwhat makes\s+\w+\s+be\b", re.IGNORECASE),
]


def run(text: str) -> list[Violation]:
    """Run all deterministic rules against the text, return all violations."""
    violations: list[Violation] = []

    violations.extend(_check_cap(text, K1_PATTERNS, K1_CAP, "K1_contrastive"))
    violations.extend(_check_cap(text, [K3_PATTERN], K3_CAP, "K3_triple_enum"))
    violations.extend(_check_hedging(text))

    violations.extend(_check_prohibited(text, K4_PATTERNS, "K4_artificial_deepening"))
    violations.extend(_check_prohibited(text, K5_PATTERNS, "K5_meta_commentary"))
    violations.extend(_check_prohibited(text, K7_PATTERNS, "K7_generic_bridges"))
    violations.extend(_check_prohibited(text, K8_PATTERNS, "K8_weak_periphrases"))

    return violations


def _check_cap(text: str, patterns: list[re.Pattern], cap: int, family: str) -> list[Violation]:
    hits = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            line = text[: match.start()].count("\n") + 1
            hits.append((line, match.group(0)))
    if len(hits) <= cap:
        return []
    # Over cap: report only the hits above cap, keeping the earliest ones silent.
    return [
        Violation(family, Severity.OVER_CAP, line, span, count=len(hits))
        for line, span in hits[cap:]
    ]


def _check_prohibited(text: str, patterns: list[re.Pattern], family: str) -> list[Violation]:
    out = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            line = text[: match.start()].count("\n") + 1
            out.append(Violation(family, Severity.PROHIBITED, line, match.group(0)))
    return out


def _check_hedging(text: str) -> list[Violation]:
    hits = []
    tokens = re.finditer(r"\b\w+\b", text)
    for match in tokens:
        if match.group(0).lower() in K6_HEDGES:
            line = text[: match.start()].count("\n") + 1
            hits.append((line, match.group(0)))
    if len(hits) <= K6_CAP:
        return []
    return [
        Violation("K6_hedging_chain", Severity.OVER_CAP, line, span, count=len(hits))
        for line, span in hits[K6_CAP:]
    ]
