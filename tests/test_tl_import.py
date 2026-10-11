from __future__ import annotations

import base64
import gzip
import json

import pytest

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

# test_kurokage_tl.py フェーズ1と同じ編成・手順(表示名とキーを混在させている)
KUROKAGE_CHARS = ["ハナコ（水着）", "Sena", "Kikyou", "アル", "リオ", "Kisaki"]
KUROKAGE_STEPS = [
    Step("Sena", note="3:54.7"),
    Step("ハナコ(水着)"),
    Step("Aru"),
    Step("Kisaki"),
    Step("Sena"),
    Step("リオ", target="ハナコ(水着)"),
    Step("リオ"),  # コピーの使用(手札上は Rio_Copy)
    Step("Hanako_Swimsuit"),
]


def _normalized():
    return normalize_inputs(KUROKAGE_CHARS, KUROKAGE_STEPS, 3)


def test_resolve_name_accepts_key_and_label() -> None:
    assert resolve_name("Hanako_Swimsuit") == "Hanako_Swimsuit"
    assert resolve_name("ハナコ（水着）") == "Hanako_Swimsuit"
    assert resolve_name(" hanako_swimsuit ") == "Hanako_Swimsuit"


def test_resolve_name_unknown_suggests_candidates() -> None:
    with pytest.raises(TLError, match="候補"):
        resolve_name("ハナコ水着")


def test_run_tl_reproduces_kurokage_phase1() -> None:
    chars, steps = _normalized()
    result = run_tl(chars, steps)

    assert result.ok, result.error
    assert [h["card"] for h in result.history] == [
        "Sena", "Hanako_Swimsuit", "Aru", "Kisaki", "Sena", "Rio", "Rio_Copy", "Hanako_Swimsuit",
    ]
    assert result.history[5]["target"] == "Hanako_Swimsuit"
    after_copy = result.history[6]["state_after"]
    assert after_copy["hand"] + after_copy["deck"] == [
        "Aru", "Hanako_Swimsuit", "Kikyou", "Kisaki", "Sena", "Rio",
    ]
    assert result.history[-1]["state_after"]["env"]["hanako_gauge"] == 100
    assert result.notes == {1: "3:54.7"}


def test_run_tl_stops_when_card_not_in_hand() -> None:
    chars, steps = normalize_inputs(KUROKAGE_CHARS, [Step("Sena"), Step("Kisaki")], 3)
    result = run_tl(chars, steps)

    assert not result.ok
    assert result.error["step"] == 2
    assert "Kisaki" not in result.error["hand"]
    assert len(result.history) == 1


def test_run_tl_warns_missing_target() -> None:
    chars, steps = normalize_inputs(KUROKAGE_CHARS, [Step("Sena"), Step("Aru"), Step("Rio")], 3)
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


def test_find_initial_orders_recovers_kurokage_order() -> None:
    chars, steps = _normalized()
    found = find_initial_orders(chars, steps)

    assert found["total_matches"] >= 1
    deck_orders = [tuple(o[3:]) for o in found["orders"]]
    assert ("Aru", "Rio", "Kisaki") in deck_orders
    for order in found["orders"]:
        assert run_tl(order, steps).ok


def test_find_initial_orders_reports_best_partial() -> None:
    # Kikyouは一度も山札から引かれないので、2回連続で使うことはできない
    chars, steps = normalize_inputs(KUROKAGE_CHARS, [Step("Kikyou"), Step("Kikyou")], 3)
    found = find_initial_orders(chars, steps)

    assert found["total_matches"] == 0
    assert found["best_partial"]["completed_steps"] == 1


def test_share_payload_roundtrip() -> None:
    chars, steps = _normalized()
    save = build_save(run_tl(chars, steps), "kurokage")
    encoded = encode_share(save)

    assert encoded.startswith("z")
    b64 = encoded[1:] + "=" * (-len(encoded[1:]) % 4)
    decoded = json.loads(gzip.decompress(base64.urlsafe_b64decode(b64)).decode("utf-8"))
    assert decoded == save
    # step1のメモは、step1の行動を表示するフレーム0に付く
    assert decoded["frame_comments"] == {"0": "3:54.7"}


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
