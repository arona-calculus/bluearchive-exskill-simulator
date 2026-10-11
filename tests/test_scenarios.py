"""
tests/data/scenarios/ 以下のTOMLシナリオを1ファイル1テストとして実行する。
シナリオの追加はTOMLを置くだけでよい(書式は scenario.py と既存のTOMLを参照)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scenario import DATA_DIR, ScenarioError, load, run_engine, scenario_paths

PATHS = scenario_paths()


def test_scenarios_exist() -> None:
    # パスの書き間違い等で1件も拾えず「全件パス」に見えるのを防ぐ
    assert PATHS, f"{DATA_DIR} にシナリオが見つかりません"


@pytest.mark.parametrize(
    "path", PATHS, ids=lambda p: p.relative_to(DATA_DIR).with_suffix("").as_posix()
)
def test_scenario(path: Path) -> None:
    run_engine(load(path))


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "typo.toml"
    path.write_text(
        'title = "typo"\ncards = ["A", "B", "C", "D"]\n'
        '[[steps]]\nslot = 0\nexpct = { cards = ["D", "B", "C", "A"] }\n',
        encoding="utf-8",
    )
    with pytest.raises(ScenarioError, match="expct"):
        load(path)


def test_wrong_expectation_fails(tmp_path: Path) -> None:
    # 照合が実際に効いていること(期待値を間違えたら落ちること)の確認
    path = tmp_path / "wrong.toml"
    path.write_text(
        'title = "wrong"\ncards = ["A", "B", "C", "D"]\n'
        '[[steps]]\nslot = 0\nexpect = { cards = ["A", "B", "C", "D"] }\n',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="cards が違います"):
        run_engine(load(path))
