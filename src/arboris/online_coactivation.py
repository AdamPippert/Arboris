# Copyright 2026 Adam Pippert & Contributors
# SPDX-License-Identifier: Apache-2.0
"""Online Space-Saving co-activation predictor and multi-stream batch deduplication.

Reference Python 3.12 implementation with exact semantic parity to the
zero-global, zero-heap seeded Omega core (`om/arboris_online.om`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

AO_NONE: int = 0xFFFFFFFF
AO_DECAY_AT: int = 60000
OP3_PREFETCH: int = 3


@dataclass(frozen=True, slots=True)
class OnlineCoactivationConfig:
    """Geometry for a bounded-memory online co-activation predictor."""

    n_trans: int
    n_experts: int
    top_k: int
    n_slots: int
    loop_from: int = AO_NONE
    loop_to: int = AO_NONE

    def is_valid(self) -> bool:
        if self.n_trans <= 0 or not (1 <= self.n_experts <= 65535):
            return False
        if not (1 <= self.top_k <= self.n_experts):
            return False
        if self.n_slots <= 0 or self.n_trans > (0x7FFFFFFF // self.n_experts):
            return False
        if self.loop_from == AO_NONE:
            return self.loop_to == AO_NONE
        if self.n_trans < 2:
            return False
        return 0 <= self.loop_from < self.n_trans and 0 <= self.loop_to < self.n_trans

    def validate(self) -> None:
        if not self.is_valid():
            raise ValueError(f"Invalid OnlineCoactivationConfig: {self!r}")

    @property
    def table_words(self) -> int:
        if not self.is_valid():
            return 0
        return self.n_trans * self.n_experts * self.n_slots


def pack_edge(count: int, target: int) -> int:
    """Pack `(count << 16) | target` into a 32-bit unsigned integer."""
    if not (0 <= count <= 0xFFFF) or not (0 <= target <= 0xFFFF):
        raise ValueError(f"Edge field out of uint16 range: count={count}, target={target}")
    return (count << 16) | target


def unpack_edge(entry: int) -> tuple[int, int]:
    """Unpack a 32-bit edge entry into `(count, target)`."""
    return (entry >> 16) & 0xFFFF, entry & 0xFFFF


@dataclass(frozen=True, slots=True)
class BatchDedupResult:
    """Deduplicated multi-stream batch activations with counts and inverse slot map."""

    unique_ids: list[int]
    counts: list[int]
    slot_map: list[int]


def dedup_batch(
    n_experts: int,
    n_streams: int,
    top_k: int,
    batch_ids: Sequence[int],
) -> BatchDedupResult:
    """Deduplicate routed expert IDs across a multi-stream batch in first-seen order."""
    if not (1 <= n_experts <= 65535) or n_streams <= 0 or top_k <= 0:
        raise ValueError(
            f"Invalid batch geometry: n_experts={n_experts}, n_streams={n_streams}, top_k={top_k}"
        )
    n_items = n_streams * top_k
    if len(batch_ids) < n_items:
        raise ValueError(f"batch_ids length {len(batch_ids)} < expected {n_items}")

    for i in range(n_items):
        eid = batch_ids[i]
        if eid != AO_NONE and not (0 <= eid < n_experts):
            raise ValueError(f"Expert ID out of range at index {i}: {eid}")

    unique_ids: list[int] = []
    counts: list[int] = []
    slot_map: list[int] = [AO_NONE] * n_items
    seen: dict[int, int] = {}

    for i in range(n_items):
        eid = batch_ids[i]
        if eid == AO_NONE:
            slot_map[i] = AO_NONE
            continue
        idx = seen.get(eid)
        if idx is None:
            idx = len(unique_ids)
            seen[eid] = idx
            unique_ids.append(eid)
            counts.append(1)
        else:
            counts[idx] += 1
        slot_map[i] = idx

    return BatchDedupResult(unique_ids=unique_ids, counts=counts, slot_map=slot_map)


class OnlineCoactivationTable:
    """Bounded Space-Saving online co-activation predictor with looped-core isolation."""

    def __init__(self, config: OnlineCoactivationConfig) -> None:
        config.validate()
        self.config = config
        self.edges: list[int] = [0] * config.table_words
        self.prev_ids: list[int] = [AO_NONE] * config.top_k
        self.prev_layer: int = config.n_trans

    def reset_token(self) -> None:
        """Clear per-token previous layer state without erasing learned co-activations."""
        self.prev_ids = [AO_NONE] * self.config.top_k
        self.prev_layer = self.config.n_trans

    def reset_all(self) -> None:
        """Zero the entire co-activation table and reset token state."""
        self.edges = [0] * self.config.table_words
        self.reset_token()

    def resolve_transition(self, prev_layer: int, layer: int) -> int:
        """Map `(prev_layer, layer)` to a transition index or `n_trans` if ignored."""
        cfg = self.config
        if not (0 <= layer < cfg.n_trans):
            return cfg.n_trans
        if layer > 0 and prev_layer + 1 == layer:
            return prev_layer
        if cfg.loop_from != AO_NONE and prev_layer == cfg.loop_from and layer == cfg.loop_to:
            return cfg.n_trans - 1
        return cfg.n_trans

    def row_base(self, trans: int, src: int) -> int:
        cfg = self.config
        return ((trans * cfg.n_experts) + src) * cfg.n_slots

    def halve_row(self, row_base: int) -> None:
        """Decay every slot in a row by halving counts (dropping count <= 1 to 0)."""
        n_slots = self.config.n_slots
        for h in range(n_slots):
            idx = row_base + h
            cnt, tgt = unpack_edge(self.edges[idx])
            self.edges[idx] = pack_edge(cnt >> 1, tgt) if cnt > 1 else 0

    def bump_edge(self, trans: int, src: int, tgt: int) -> None:
        """Increment or Space-Saving-insert edge `(src -> tgt)` on transition `trans`."""
        cfg = self.config
        if not (0 <= trans < cfg.n_trans and 0 <= src < cfg.n_experts and 0 <= tgt < cfg.n_experts):
            return
        base = self.row_base(trans, src)
        n_slots = cfg.n_slots

        for j in range(n_slots):
            idx = base + j
            cnt, cur_tgt = unpack_edge(self.edges[idx])
            if cnt > 0 and cur_tgt == tgt:
                nc = cnt + 1
                if nc >= AO_DECAY_AT:
                    self.halve_row(base)
                    nc = AO_DECAY_AT >> 1
                self.edges[idx] = pack_edge(nc, tgt)
                return

        empty_slot = n_slots
        min_slot = 0
        min_cnt = 65536
        for j in range(n_slots):
            cnt, _ = unpack_edge(self.edges[base + j])
            if cnt == 0:
                if empty_slot == n_slots:
                    empty_slot = j
            elif cnt < min_cnt:
                min_cnt = cnt
                min_slot = j

        if empty_slot < n_slots:
            self.edges[base + empty_slot] = pack_edge(1, tgt)
            return

        if min_cnt <= 1:
            self.edges[base + min_slot] = pack_edge(1, tgt)
        else:
            _, old_tgt = unpack_edge(self.edges[base + min_slot])
            self.edges[base + min_slot] = pack_edge(min_cnt - 1, old_tgt)

    def observe(self, layer: int, cur_ids: Sequence[int]) -> int:
        """Observe active experts at `layer`, update edges if valid, and advance state."""
        cfg = self.config
        if not (0 <= layer < cfg.n_trans):
            raise ValueError(f"layer {layer} out of range 0..{cfg.n_trans - 1}")
        if len(cur_ids) < cfg.top_k:
            raise ValueError(f"cur_ids length {len(cur_ids)} < top_k {cfg.top_k}")

        trans = self.resolve_transition(self.prev_layer, layer)
        if trans < cfg.n_trans:
            for s in range(cfg.top_k):
                src = self.prev_ids[s]
                if 0 <= src < cfg.n_experts:
                    for d in range(cfg.top_k):
                        tgt = cur_ids[d]
                        if 0 <= tgt < cfg.n_experts:
                            self.bump_edge(trans, src, tgt)

        self.prev_ids = [int(cur_ids[k]) for k in range(cfg.top_k)]
        self.prev_layer = layer
        return trans

    def score_src(self, trans: int, src: int, scores: list[int], weight: int = 1) -> None:
        """Accumulate weighted co-activation counts from one source row into `scores`."""
        cfg = self.config
        if not (0 <= trans < cfg.n_trans and 0 <= src < cfg.n_experts):
            raise ValueError(f"Invalid (trans, src): ({trans}, {src})")
        if len(scores) < cfg.n_experts:
            raise ValueError(f"scores length {len(scores)} < n_experts {cfg.n_experts}")
        base = self.row_base(trans, src)
        for j in range(cfg.n_slots):
            cnt, tgt = unpack_edge(self.edges[base + j])
            if cnt > 0 and tgt < cfg.n_experts:
                scores[tgt] += cnt * weight

    def score_batch(self, trans: int, src_ids: Sequence[int]) -> list[int]:
        """Compute sum-over-paths scores across all active `src_ids` on transition `trans`."""
        cfg = self.config
        if not (0 <= trans < cfg.n_trans):
            raise ValueError(f"trans {trans} out of range 0..{cfg.n_trans - 1}")
        scores = [0] * cfg.n_experts
        for src in src_ids:
            if src == AO_NONE:
                continue
            if not (0 <= src < cfg.n_experts):
                raise ValueError(f"Source expert ID out of range: {src}")
            self.score_src(trans, src, scores, weight=1)
        return scores


def mask_resident(
    config: OnlineCoactivationConfig,
    next_layer: int,
    resident: Sequence[int],
    scores: list[int],
) -> None:
    """Zero scores for experts already resident in `next_layer` (`resident[idx] >= 0`).

    An empty `resident` sequence is accepted as a no-op (no experts masked).
    """
    config.validate()
    if not (0 <= next_layer < config.n_trans):
        raise ValueError(f"next_layer {next_layer} out of range 0..{config.n_trans - 1}")
    if len(scores) < config.n_experts:
        raise ValueError(f"scores length {len(scores)} < n_experts {config.n_experts}")
    if len(resident) == 0:
        return
    base = next_layer * config.n_experts
    if len(resident) < base + config.n_experts:
        raise ValueError(
            f"resident length {len(resident)} < required {base + config.n_experts}"
        )
    for eid in range(config.n_experts):
        if resident[base + eid] >= 0:
            scores[eid] = 0


def pick_op3_hints(
    config: OnlineCoactivationConfig,
    scores: list[int],
    budget: int,
) -> list[tuple[int, int]]:
    """Select up to `budget` non-zero experts as `(OP3_PREFETCH, eid)` hints.

    Consumes picked scores in-place (zeroing them) and breaks ties by lowest expert ID.
    """
    config.validate()
    if budget < 0:
        raise ValueError(f"budget must be >= 0, got {budget}")
    if len(scores) < config.n_experts:
        raise ValueError(f"scores length {len(scores)} < n_experts {config.n_experts}")

    hints: list[tuple[int, int]] = []
    for _ in range(budget):
        best_id = config.n_experts
        best_score = 0
        for eid in range(config.n_experts):
            sc = scores[eid]
            if sc > best_score:
                best_score = sc
                best_id = eid
        if best_id == config.n_experts:
            break
        hints.append((OP3_PREFETCH, best_id))
        scores[best_id] = 0
    return hints
