# RFC: Online Co-Activation Prediction, Looped-Core Isolation, and Cross-Batch Deduplication

- **Status:** Draft proposal for `AdamPippert/Arboris`
- **Target stages:** `docs/migration_plan.md` Stage 3 (Dendritron & hypotheses) and Stage 6 (Routing, packs, and expansion)
- **License:** Apache-2.0
- **Reference parity:** Matches the zero-global, zero-heap seeded Omega implementation in `omega-mv` (`om/arboris_online.om`, commit `8aa3aeb4125a77cdcd942eb3b3dc91fb97d1f1c9`)

## Motivation

When branching or routed architectures execute across sequential layers (including looped recurrent cores) and multi-stream batches, two runtime bottlenecks dominate speculative prefetching and routing:

1. **Transition interference in looped cores:** A layer transition `L_from -> L_to` (for example, wrapping from layer 17 back to layer 6 across recurrent passes) has different co-activation structure than the exit transition `L_from -> L_from + 1`. Conflating both into a single transition table degrades prediction precision.
2. **Duplicate work across concurrent streams:** In a multi-stream batch (`n_streams * top_k` routed activations), hot branches/experts are frequently selected by multiple streams simultaneously. Deduplicating across the batch before loading or scoring avoids redundant I/O and provides exact multiplicity counts for batch-aware arbitration.

## Proposed Primitives

This RFC proposes a small, dependency-free, deterministic online co-activation module (`src/arboris/online_coactivation.py`) with four orthogonal capabilities:

### 1. Parameterized Geometry (`OnlineCoactivationConfig`)
A fixed 6-tuple configuration defines the predictor geometry with no hidden globals:
- `n_trans >= 1`: number of transition tables (`0 .. n_trans - 2` for adjacent `L -> L + 1`; `n_trans - 1` reserved for an optional looped wrap).
- `n_experts` in `1 .. 65535`: number of experts/branches per layer (bounded by 16-bit target packing).
- `top_k` in `1 .. n_experts`: active activations per layer per stream.
- `n_slots >= 1`: bounded Space-Saving slots per `(transition, source)` row.
- `loop_from`, `loop_to`: either both `AO_NONE` (`0xFFFFFFFF`, non-looped) or both valid layer indices `< n_trans` with `n_trans >= 2`.

### 2. Bounded Space-Saving Co-Activation Table (`OnlineCoactivationTable`)
- Each slot packs `(count << 16) | target_id` into a 32-bit unsigned integer (`n_trans * n_experts * n_slots` words total).
- On a hit, `count` increments; when `count` reaches `AO_DECAY_AT` (`60000`), the entire row halves (`count >> 1`, dropping entries whose count falls to `0`) and the bumped entry settles at `30000`, allowing online adaptation to domain shifts without overflow.
- On a miss, the first empty slot is populated with count `1`; if the row is full, the minimum-count slot is replaced if `min_cnt <= 1`, otherwise decremented by `1` (Space-Saving heavy-hitter retention).
- **Transition resolution (`resolve_transition`):**
  - Adjacent `layer > 0 and prev_layer + 1 == layer` resolves to `prev_layer`.
  - Looped wrap `prev_layer == loop_from and layer == loop_to` resolves to `n_trans - 1`.
  - Repeated layers, skipped layers, and cross-token transitions after `reset_token()` resolve to sentinel `n_trans` and update `prev_ids` without corrupting edge counts.

### 3. Cross-Batch Deduplication (`dedup_batch`)
Given a flattened multi-stream batch of `n_streams * top_k` routed IDs (with `AO_NONE` marking inactive slots):
- Validates every active ID is `< n_experts` before returning any result.
- Emits:
  - `unique_ids`: unique active expert IDs in deterministic first-seen order.
  - `counts`: batch multiplicity per unique expert.
  - `slot_map`: inverse map from each batch position `0 .. n_items - 1` to its slot in `unique_ids` (or `AO_NONE` if inactive).

### 4. Sum-Over-Paths Scoring, Residency Masking, and Deterministic `OP3` Hints
- `score_batch(trans, src_ids)` accumulates co-activation counts across all active source IDs in `src_ids` (e.g., `dedup_result.unique_ids`) into a per-expert score vector.
- `mask_resident(config, next_layer, resident, scores)` zeros scores for already-resident entries (`resident[next_layer * n_experts + eid] >= 0`), cleanly accepting an empty `resident` sequence when no residency table is attached.
- `pick_op3_hints(config, scores, budget)` greedily emits up to `budget` advisory `(3, target_id)` records in strictly descending score order, breaking exact ties deterministically by lowest `target_id` and stopping once remaining scores are `0`.

## Integration Path with Existing Arboris Stages

- **Zero new dependencies:** Uses only Python 3.12 standard library types, preserving `pyproject.toml` and `uv.lock` untouched.
- **Ablatable & deterministic:** Every state transition and tie break is 100% deterministic, matching the Stage 1–3 acceptance philosophy in `docs/migration_plan.md`.
- **Clean bridge to Stage 3/6:** Can serve as a fast non-neural baseline predictor/prefetcher beside Stage 3 dendritic branches and Stage 6 memory-pack routing.
