"""Keyword retrieval over the local recipe notes.

Deliberately not a vector database: a tf-idf scorer over markdown sections is
~80 lines, has no model dependency, and every retrieval decision is inspectable
in a trace. That transparency is the point of the tutorial.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from strands import tool

RECIPES_DIR = Path(__file__).resolve().parents[3] / "recipes"

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "means",
        "of",
        "on",
        "or",
        "so",
        "than",
        "that",
        "the",
        "then",
        "this",
        "to",
        "was",
        "when",
        "which",
        "will",
        "with",
        "your",
        "you",
    ]
)

_WORD = re.compile(r"[a-z0-9°:]+")


@dataclass
class Chunk:
    source: str
    heading: str
    text: str
    tokens: Counter = field(default_factory=Counter)


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def load_corpus(recipes_dir: Path = RECIPES_DIR) -> list[Chunk]:
    """Split each recipe file into chunks on '## ' headings."""
    chunks: list[Chunk] = []
    for path in sorted(recipes_dir.glob("*.md")):
        heading = "intro"
        lines: list[str] = []
        for line in path.read_text().splitlines():
            if line.startswith("## "):
                if lines and any(ln.strip() for ln in lines):
                    text = "\n".join(lines).strip()
                    chunks.append(Chunk(path.name, heading, text, Counter(_tokenize(text))))
                heading = line[3:].strip()
                lines = []
            elif line.startswith("# "):
                continue
            else:
                lines.append(line)
        if lines and any(ln.strip() for ln in lines):
            text = "\n".join(lines).strip()
            chunks.append(Chunk(path.name, heading, text, Counter(_tokenize(text))))
    return chunks


_corpus_cache: list[Chunk] | None = None


def _corpus() -> list[Chunk]:
    global _corpus_cache
    if _corpus_cache is None:
        _corpus_cache = load_corpus()
    return _corpus_cache


def search(query: str, k: int = 3, chunks: list[Chunk] | None = None) -> list[tuple[Chunk, float]]:
    """Rank chunks by tf-idf: score = sum over query terms of tf(term) * idf(term)."""
    corpus = chunks if chunks is not None else _corpus()
    n = len(corpus)
    scored: list[tuple[Chunk, float]] = []
    terms = _tokenize(query)
    for chunk in corpus:
        score = 0.0
        for term in terms:
            tf = chunk.tokens.get(term, 0)
            if tf:
                df = sum(1 for c in corpus if term in c.tokens)
                score += tf * math.log(n / df)
        if score > 0:
            scored.append((chunk, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]


@tool
def retrieve_recipe_notes(query: str, k: int = 3) -> str:
    """Search the local coffee recipe notes for guidance relevant to a query.

    Args:
        query: What to look up, e.g. "v60 sour thin underextraction" or
            "stalled drawdown fix"
        k: Number of note sections to return
    """
    results = search(query, k=k)
    if not results:
        return "No matching recipe notes found."
    return "\n\n".join(f"[{c.source} § {c.heading}]\n{c.text}" for c, _ in results)
