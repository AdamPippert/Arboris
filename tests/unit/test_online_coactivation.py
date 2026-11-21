# Copyright 2026 Adam Pippert & Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for online Space-Saving co-activation and multi-stream deduplication."""

from __future__ import annotations

import pytest

from arboris.online_coactivation import (
    AO_DECAY_AT,
    AO_NONE,
    OP3_PREFETCH,
    OnlineCoactivationConfig,
    OnlineCoactivationTable,
    dedup_batch,
    mask_resident,
    pack_edge,
    pick_op3_hints,
    unpack_edge,
)


def _inkling_cfg() -> OnlineCoactivationConfig:
    return OnlineCoactivationConfig(
        n_trans=24,
        n_experts=128,
        top_k=8,
        n_slots=16,
        loop_from=17,
        loop_to=6,
    )


def _deepseek_cfg() -> OnlineCoactivationConfig:
    return OnlineCoactivationConfig(
        n_trans=4,
        n_experts=384,
        top_k=6,
        n_slots=16,
        loop_from=AO_NONE,
        loop_to=AO_NONE,
    )


def test_single_stream_and_looped_core_isolation() -> None:
    cfg = _inkling_cfg()
    assert cfg.is_valid()
    assert cfg.table_words == 49152

    tbl = OnlineCoactivationTable(cfg)
    assert tbl.resolve_transition(17, 6) == 23
    assert tbl.resolve_transition(17, 18) == 17
    assert tbl.resolve_transition(23, 0) == 24

    ids_a = [10 + k for k in range(8)]
    ids_b = [20 + k for k in range(8)]
    ids_c = [30 + k for k in range(8)]

    # Adjacent observation 0 -> 1 builds transition 0
    assert tbl.observe(0, ids_a) == 24
    assert tbl.observe(1, ids_b) == 0

    # Looped wrap 17 -> 6 trains isolated transition 23, leaving 17 -> 18 untouched
    tbl.reset_token()
    assert tbl.observe(17, ids_a) == 24
    assert tbl.observe(6, ids_c) == 23
    # Repeated layer 6 -> 6 is ignored
    assert tbl.observe(6, ids_b) == 24

    scores_wrap = tbl.score_batch(23, ids_a)
    assert scores_wrap[30] == 8

    scores_exit = tbl.score_batch(17, ids_a)
    assert scores_exit[30] == 0

    # Mark expert 30 resident in layer 6 -> lowest-ID tie break picks 31, then 32
    resident = [-1] * (24 * 128)
    resident[6 * 128 + 30] = 0
    mask_resident(cfg, 6, resident, scores_wrap)
    hints = pick_op3_hints(cfg, scores_wrap, budget=2)
    assert hints == [(OP3_PREFETCH, 31), (OP3_PREFETCH, 32)]


def test_saturation_halving_and_space_saving_eviction() -> None:
    cfg = _inkling_cfg()
    tbl = OnlineCoactivationTable(cfg)

    # Saturation halving at AO_DECAY_AT (60000 -> 30000)
    base = tbl.row_base(6, 4)
    tbl.edges[base] = pack_edge(AO_DECAY_AT - 1, 77)
    tbl.bump_edge(6, 4, 77)
    assert unpack_edge(tbl.edges[base]) == (AO_DECAY_AT >> 1, 77)

    # Space-Saving replacement on a full row when min_cnt == 1
    tbl.reset_all()
    for i in range(16):
        tbl.bump_edge(5, 3, 10 + i)
    tbl.bump_edge(5, 3, 99)
    tbl.bump_edge(5, 3, 99)
    scores = tbl.score_batch(5, [3])
    assert scores[99] == 2


def test_multistream_dedup_and_sum_over_paths_ranking() -> None:
    cfg = _deepseek_cfg()
    assert cfg.is_valid()
    assert cfg.table_words == 24576

    tbl = OnlineCoactivationTable(cfg)
    for _ in range(2):
        tbl.bump_edge(1, 10, 100)
    for _ in range(3):
        tbl.bump_edge(1, 20, 200)
    tbl.bump_edge(1, 20, 105)
    for _ in range(4):
        tbl.bump_edge(1, 70, 55)

    # 4 streams * top_k 6 = 24 slots with shared hot experts and AO_NONE padding
    batch_ids = [AO_NONE] * 24
    batch_ids[0:3] = [10, 20, 30]
    batch_ids[6:9] = [20, 30, 70]
    batch_ids[12:15] = [10, 70, 110]
    batch_ids[18:21] = [20, 110, 120]

    dedup = dedup_batch(n_experts=384, n_streams=4, top_k=6, batch_ids=batch_ids)
    assert dedup.unique_ids == [10, 20, 30, 70, 110, 120]
    assert dedup.counts == [2, 3, 2, 2, 2, 1]
    assert dedup.slot_map[18] == 1  # batch slot 18 (expert 20) -> unique slot 1
    assert dedup.slot_map[3] == AO_NONE

    scores = tbl.score_batch(1, dedup.unique_ids)
    # Empty resident slice is a valid no-op
    mask_resident(cfg, 2, [], scores)
    hints = pick_op3_hints(cfg, scores, budget=4)
    assert hints == [
        (OP3_PREFETCH, 55),
        (OP3_PREFETCH, 200),
        (OP3_PREFETCH, 100),
        (OP3_PREFETCH, 105),
    ]


def test_negative_controls_config_and_buffers() -> None:
    assert not OnlineCoactivationConfig(0, 128, 8, 16, 17, 6).is_valid()
    assert not OnlineCoactivationConfig(24, 65536, 8, 16, 17, 6).is_valid()
    assert not OnlineCoactivationConfig(24, 128, 200, 16, 17, 6).is_valid()
    assert not OnlineCoactivationConfig(24, 128, 8, 16, AO_NONE, 6).is_valid()

    with pytest.raises(ValueError):
        OnlineCoactivationTable(OnlineCoactivationConfig(0, 128, 8, 16))

    with pytest.raises(ValueError):
        dedup_batch(384, 2, 4, [0, 1, 2, 3, 4, 384, 6, 7])

    with pytest.raises(ValueError):
        dedup_batch(384, 2, 4, [0, 1, 2])

    cfg = _inkling_cfg()
    scores = [0] * 128
    with pytest.raises(ValueError):
        mask_resident(cfg, 1, [-1] * 128, scores)
    with pytest.raises(ValueError):
        mask_resident(cfg, 24, [-1] * (24 * 128), scores)
    with pytest.raises(ValueError):
        pick_op3_hints(cfg, scores, budget=-1)
