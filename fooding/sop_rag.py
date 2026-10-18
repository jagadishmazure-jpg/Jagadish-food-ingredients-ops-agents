"""TF-IDF retrieval over the 4 SOP docs, with citations and explicit not-found.

Citations look like `sop-02-substitution-guidelines.md §Scoring`.
Title-only chunks (a bare H1 with no body) are skipped at load time —
they caused a false positive in a sibling repo ("policy" matching a
title-only intro).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

_SOP_DIR = Path(__file__).resolve().parents[1] / "docs" / "sops"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]{2,}", text.lower())


def load_chunks() -> list[dict]:
    """Split each SOP into ## sections; skip title-only intros."""
    chunks = []
    for path in sorted(_SOP_DIR.glob("sop-*.md")):
        text = path.read_text()
        parts = re.split(r"^## ", text, flags=re.MULTILINE)
        intro = parts[0]
        # skip the title-only intro (no body text under the H1)
        body = re.sub(r"^#.*$", "", intro, flags=re.MULTILINE).strip()
        if body:
            chunks.append({"file": path.name, "section": "Purpose",
                           "text": body})
        for part in parts[1:]:
            lines = part.split("\n", 1)
            section = lines[0].strip()
            sect_text = lines[1].strip() if len(lines) > 1 else ""
            if sect_text:
                chunks.append({"file": path.name, "section": section,
                               "text": sect_text})
    return chunks


def _tfidf_vectors(chunks: list[dict]):
    docs = [_tokenize(c["text"]) for c in chunks]
    df = Counter()
    for toks in docs:
        for t in set(toks):
            df[t] += 1
    n = len(docs)
    vecs = []
    for toks in docs:
        tf = Counter(toks)
        vec = {t: (f / len(toks)) * math.log(n / df[t]) for t, f in tf.items()}
        vecs.append(vec)
    return vecs


def retrieve(query: str, top_k: int = 2, min_score: float = 0.05) -> list[dict]:
    """Return top-k chunks with citations. Empty list = explicit not-found."""
    chunks = load_chunks()
    if not chunks:
        return []
    vecs = _tfidf_vectors(chunks)
    qtoks = Counter(_tokenize(query))
    scored = []
    for chunk, vec in zip(chunks, vecs):
        score = sum(vec.get(t, 0.0) * f for t, f in qtoks.items())
        if score >= min_score:
            scored.append((score, chunk))
    scored.sort(key=lambda s: s[0], reverse=True)
    out = []
    for score, chunk in scored[:top_k]:
        out.append({
            "citation": f"{chunk['file']} §{chunk['section']}",
            "score": round(score, 4),
            "text": " ".join(chunk["text"].split()[:60]),
        })
    return out
