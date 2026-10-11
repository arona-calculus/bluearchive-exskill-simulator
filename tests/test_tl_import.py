from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import pytest

import scenario as sc
from webui.backend.tl_import import (
    Step,
    TLError,
    build_save,
    encode_share,
    find_initial_orders,
    normalize_inputs,
    resolve_name,
    run_tl,
)

KUROKAGE_PHASE1 = sc.load(sc.SCENARIO_DIR / "kurokage" / "phase1.toml")
# ラフTLでの書き方: 表示名で書き、リオのコピーの使用も単に「リオ」と書く
ROUGH_NAMES = {
    "Hanako_Swimsuit": "ハナコ（水着）",
    "Aru": "アル",
    "Rio": "リオ",
    "Rio_Copy": "リオ",
}


def _tl_steps(scenario: sc.Scenario, keep_slot: bool = True) -> list[Step]:
    return [Step(**d) for d in sc.step_inputs(scenario, keep_slot=keep_slot)]


def _history_outputs(result) -> list[dict]:
    return [
        {
            "cost": h["cost"],
            "hand": h["state_after"]["hand"],
            "deck": h["state_after"]["deck"],
            "env": h["state_after"]["env"],
        }
        for h in result.history
    ]


def _check(scenario: sc.Scenario, result) -> None:
    sc.check_tl_result(
        scenario, result.ok, result.error, _history_outputs(result), result.current_state
    )


def _kurokage_phase1_rough() -> tuple[list[str], list[Step]]:
    """黒影フェーズ1を、スロット指定なし・表示名混じりのラフな書き方にしたもの。"""
    chars = [ROUGH_NAMES.get(c, c) for c in KUROKAGE_PHASE1.cards]
    steps = [
        Step(ROUGH_NAMES.get(s.card, s.card), target=s.target, note=s.note)
        for s in KUROKAGE_PHASE1.steps
    ]
    return normalize_inputs(chars, steps, KUROKAGE_PHASE1.hand_size)


# ---------------------------------------------------------------------------
# 名前解決
# ---------------------------------------------------------------------------


def test_resolve_name_accepts_key_and_label() -> None:
    assert resolve_name("Hanako_Swimsuit") == "Hanako_Swimsuit"
    assert resolve_name("ハナコ（水着）") == "Hanako_Swimsuit"
    assert resolve_name(" hanako_swimsuit ") == "Hanako_Swimsuit"


def test_resolve_name_unknown_suggests_candidates() -> None:
    with pytest.raises(TLError, match="候補"):
        resolve_name("ハナコ水着")


# ---------------------------------------------------------------------------
# run_tl
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    sc.scenario_paths(),
    ids=lambda p: p.relative_to(sc.DATA_DIR).with_suffix("").as_posix(),
)
def test_run_tl_agrees_with_engine_scenarios(path: Path) -> None:
    # エンジンの回帰シナリオを、同じSpecで run_tl 経由でも実行して同じ期待値で照合する
    scenario = sc.load(path)
    result = run_tl(
        scenario.cards,
        _tl_steps(scenario),
        scenario.hand_size,
        scenario.env,
        specs=sc.build_specs(scenario),
    )

    error_steps = [i for i, s in enumerate(scenario.steps, start=1) if "error" in s.expect]
    if error_steps:
        # run_tl は最初の例外で止まる
        assert result.error and result.error["step"] == error_steps[0], result.error
        assert len(result.history) == error_steps[0] - 1
        return
    assert result.ok, result.error
    _check(scenario, result)


def test_run_tl_resolves_labels_and_rio_copy() -> None:
    # 表示名、および「リオ」と書かれたコピーの使用(手札上は Rio_Copy)を解決して、
    # スロット指定ありのシナリオと同じ結果になること
    chars, steps = _kurokage_phase1_rough()
    result = run_tl(chars, steps)

    assert [h["card"] for h in result.history][5:7] == ["Rio", "Rio_Copy"]
    _check(KUROKAGE_PHASE1, result)
    assert result.notes == {i: s.note for i, s in enumerate(KUROKAGE_PHASE1.steps, start=1)}


def test_run_tl_stops_when_card_not_in_hand() -> None:
    chars, steps = normalize_inputs(KUROKAGE_PHASE1.cards, [Step("Sena"), Step("Kisaki")], 3)
    result = run_tl(chars, steps)

    assert not result.ok
    assert result.error["step"] == 2
    assert "Kisaki" not in result.error["hand"]
    assert len(result.history) == 1


def test_run_tl_warns_missing_target() -> None:
    chars, steps = normalize_inputs(
        KUROKAGE_PHASE1.cards, [Step("Sena"), Step("Aru"), Step("Rio")], 3
    )
    result = run_tl(chars, steps)

    assert result.ok
    assert "対象未指定" in result.notes[3]


def test_run_tl_no_warning_for_ibuki_ex2() -> None:
    chars, steps = normalize_inputs(
        ["Ibuki_Swimsuit", "Aru", "Kisaki", "Sena"],
        [Step("Ibuki_Swimsuit", target="Aru"), Step("Ibuki_Swimsuit")],
        3,
    )
    result = run_tl(chars, steps)

    assert result.ok, result.error
    assert result.notes == {}


@pytest.mark.parametrize("path", sorted(sc.TL_DIR.glob("*.toml")), ids=lambda p: p.stem)
def test_tl_cases(path: Path) -> None:
    # data/tl の実戦TL(実カタログ・表示名混じり)を MCP と同じ経路で実行する
    scenario = sc.load(path)
    chars, steps = normalize_inputs(scenario.cards, _tl_steps(scenario), scenario.hand_size)
    _check(scenario, run_tl(chars, steps, scenario.hand_size, scenario.env))


# ---------------------------------------------------------------------------
# find_initial_orders
# ---------------------------------------------------------------------------


def test_find_initial_orders_recovers_kurokage_order() -> None:
    chars, steps = _kurokage_phase1_rough()
    found = find_initial_orders(chars, steps)

    assert found["total_matches"] >= 1
    deck_orders = [o[3:] for o in found["orders"]]
    assert KUROKAGE_PHASE1.cards[3:] in deck_orders
    for order in found["orders"]:
        assert run_tl(order, steps).ok


def test_find_initial_orders_reports_best_partial() -> None:
    # Kikyouは一度も山札から引かれないので、2回連続で使うことはできない
    chars, steps = normalize_inputs(
        KUROKAGE_PHASE1.cards, [Step("Kikyou"), Step("Kikyou")], 3
    )
    found = find_initial_orders(chars, steps)

    assert found["total_matches"] == 0
    assert found["best_partial"]["completed_steps"] == 1


# ---------------------------------------------------------------------------
# webui連携
# ---------------------------------------------------------------------------


def test_share_payload_roundtrip() -> None:
    chars, steps = _kurokage_phase1_rough()
    save = build_save(run_tl(chars, steps), "kurokage")
    encoded = encode_share(save)

    assert encoded.startswith("z")
    b64 = encoded[1:] + "=" * (-len(encoded[1:]) % 4)
    decoded = json.loads(gzip.decompress(base64.urlsafe_b64decode(b64)).decode("utf-8"))
    assert decoded == save
    # step i のメモは、step i の行動を表示するフレーム i-1 に付く
    assert decoded["frame_comments"]["0"] == KUROKAGE_PHASE1.steps[0].note


def test_custom_specs_match_webui_catalog() -> None:
    # scenario.py の CUSTOM_SPECS が webui の固有Spec割り当てと食い違っていないこと
    from ba_exsim.specs.generic import GenericSpec
    from webui.backend.catalog import BUILTINS

    webui_custom = {k: e.spec for k, e in BUILTINS.items() if e.spec is not GenericSpec}
    assert webui_custom == sc.CUSTOM_SPECS


def test_webui_play_endpoint_still_works() -> None:
    from fastapi.testclient import TestClient

    from webui.backend.main import app

    client = TestClient(app)
    res = client.post("/api/session", json={"characters": ["Rio", "Aru", "Kisaki", "Sena"]})
    session_id = res.json()["session_id"]
    res = client.post(f"/api/session/{session_id}/play", json={"slot": 0, "target": "Aru"})

    assert res.status_code == 200
    body = res.json()
    assert body["played_card"] == "Rio"
    assert body["state"]["hand"][0] == "Rio_Copy"
    assert body["history"][0]["cumulative_cost"] == (body["history"][0]["cost"] or 0)
