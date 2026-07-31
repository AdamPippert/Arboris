"""Reference providers: deterministic, dependency-free, honest about what
they are.

These exist so the pipeline is runnable and testable end-to-end with zero
model dependencies — in CI, on a laptop, in a design review. They implement
the same protocols a real dense or late-interaction model adapter implements,
and they are registered in the same registry, so swapping in "denseon" /
"mdenseon" / "lateon" / "mlateon" (or anything else) is a configuration
change, not a code change. They are NOT competitive retrievers and never
will be.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

from . import registry
from .graph import InMemoryGraphStore
from .types import Candidate, Evidence, Query, Scale

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DIM = 64


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _token_vec(token: str) -> list[float]:
    """Pseudo-embedding: hash the token into a fixed unit vector."""
    digest = hashlib.sha256(token.encode()).digest()
    vec = [b / 255.0 - 0.5 for b in digest[:_DIM]]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class HashEmbeddingProvider:
    """EmbeddingProvider: mean of hashed token vectors (bag-of-words-like)."""

    name = "hash"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out = []
        for text in texts:
            toks = _tokens(text) or [""]
            vecs = [_token_vec(t) for t in toks]
            mean = [sum(col) / len(vecs) for col in zip(*vecs)]
            norm = math.sqrt(sum(v * v for v in mean)) or 1.0
            out.append([v / norm for v in mean])
        return out


class HashLateInteraction:
    """LateInteractionProvider: maxsim over hashed token vectors — the same
    interaction pattern as real late-interaction models, minus the learning."""

    name = "hash-late"
    scales = (Scale.NODE, Scale.EDGE, Scale.SENTENCE, Scale.DOCUMENT)

    def score(self, query: str, items: Sequence[str]) -> list[float]:
        q_vecs = [_token_vec(t) for t in _tokens(query)] or [[0.0] * _DIM]
        scores = []
        for item in items:
            i_vecs = [_token_vec(t) for t in _tokens(item)]
            if not i_vecs:
                scores.append(0.0)
                continue
            total = sum(max(_cosine(q, iv) for iv in i_vecs) for q in q_vecs)
            scores.append(total / len(q_vecs))
        return scores


class GraphDenseRetriever:
    """DenseRetriever over a GraphStore's node texts (stage-1 recall)."""

    def __init__(self, store: InMemoryGraphStore, provider=None, name: str = "graph-dense"):
        self.name = name
        self.store = store
        self.provider = provider or HashEmbeddingProvider()
        ids = sorted(store.node_ids())
        vecs = self.provider.embed([store.node_text(i) for i in ids])
        self._index = list(zip(ids, vecs))

    async def retrieve(self, query: Query, limit: int) -> list[Candidate]:
        qv = self.provider.embed([query.text])[0]
        scored = sorted(
            ((_cosine(qv, vec), node_id) for node_id, vec in self._index),
            key=lambda t: (-t[0], t[1]),
        )
        return [
            Candidate(item_id=node_id, scale=Scale.NODE, score=score, provider=self.name)
            for score, node_id in scored[:limit]
        ]


class GraphLateInteractionRetriever:
    """LateInteractionRetriever over candidates' node AND incident-edge texts
    (stage-2 precision). Scores node<->query and edge<->query channels and
    keeps them separate in the Evidence record."""

    def __init__(self, store: InMemoryGraphStore, provider=None, name: str = "graph-late"):
        self.name = name
        self.store = store
        self.provider = provider or HashLateInteraction()

    async def rerank(self, query: Query, candidates: Sequence[Candidate]) -> list[Evidence]:
        out = []
        node_ids = [c.item_id for c in candidates]
        node_scores = self.provider.score(query.text, [self.store.node_text(i) for i in node_ids])
        for cand, node_score in zip(candidates, node_scores):
            edge_ids = sorted(e["id"] for e in self.store.neighbors(cand.item_id))
            edge_score = 0.0
            if edge_ids:
                edge_score = max(
                    self.provider.score(query.text, [self.store.edge_text(e) for e in edge_ids])
                )
            score = 0.7 * node_score + 0.3 * edge_score
            out.append(
                Evidence(
                    item_id=cand.item_id,
                    kind="node",
                    scale=cand.scale,
                    score=score,
                    channels={
                        f"{self.name}:node": node_score,
                        f"{self.name}:edge": edge_score,
                        f"recall:{cand.provider}": cand.score,
                    },
                )
            )
        return out


registry.embedding_providers.register("hash", HashEmbeddingProvider)
registry.late_interaction_providers.register("hash-late", HashLateInteraction)
registry.dense_retrievers.register("graph-dense", GraphDenseRetriever)
registry.late_interaction_retrievers.register("graph-late", GraphLateInteractionRetriever)
