"""
tests/data/ 以下のTOMLシナリオ(編成・初期の手札+山札順・手順・期待値)を読み込み、実行・照合する共通部品。

- data/scenarios/: エンジンの回帰シナリオ。run_engine() で Simulator を直接駆動する。

スキーマは load() 内の *_KEYS を参照。未知のキーは書き間違いとみなしてロード時にエラーにする。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State
from ba_exsim.specs.alice_battle import AliceBattleSpec
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.ibuki_swimsuit import IbukiSwimsuitSpec
from ba_exsim.specs.rio import RioCopySpec, RioSpec
from ba_exsim.specs.yuzu_battle import YuzuBattleSpec

DATA_DIR = Path(__file__).parent / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"

# 固有Specを割り当てる生徒(webui の BUILTINS のうち GenericSpec 以外のもの)。それ以外は GenericSpec。
# 生成データ(characters.json)には依存しないので、再生成してもシナリオは壊れない
CUSTOM_SPECS: Dict[str, type] = {
    "Alice_Battle": AliceBattleSpec,
    "Hanako_Swimsuit": HanakoSwimsuitSpec,
    "Ibuki_Swimsuit": IbukiSwimsuitSpec,
    "Rio": RioSpec,
    "Yuzu_Battle": YuzuBattleSpec,
}

TOP_KEYS = {
    "title", "description", "hand_size", "cards", "env",
    "rough_tl", "verified", "overrides", "steps", "expect",
}
STEP_KEYS = {"card", "slot", "target", "note", "expect"}
STEP_EXPECT_KEYS = {
    "cards", "hand", "deck", "hand_excludes", "env", "env_none",
    "cost", "cost_unknown", "error", "error_match",
}
FINAL_EXPECT_KEYS = {"total_cost", "cards", "hand", "deck", "hand_excludes", "env", "env_none"}
OVERRIDE_KEYS = {"cost", "extra_cost", "role"}


class ScenarioError(ValueError):
    """シナリオファイル自体の不備(未知のキー、必須項目の欠落など)"""


@dataclass
class Step:
    card: str = ""
    slot: Optional[int] = None
    target: str = ""
    note: str = ""
    expect: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    path: Path
    title: str
    cards: List[str]
    steps: List[Step]
    hand_size: int = 3
    env: Dict[str, Any] = field(default_factory=dict)
    overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    description: str = ""
    rough_tl: str = ""
    verified: Optional[bool] = None
    expect: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """data/ からの相対パス(拡張子なし)。pytestのidやエラーメッセージに使う。"""
        try:
            return self.path.relative_to(DATA_DIR).with_suffix("").as_posix()
        except ValueError:
            return self.path.stem


def _check_keys(where: str, data: Dict[str, Any], allowed: set) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ScenarioError(f"{where}: 未知のキー {unknown} (使えるキー: {sorted(allowed)})")


def load(path: Path) -> Scenario:
    with path.open("rb") as f:
        data = tomllib.load(f)
    where = path.as_posix()
    _check_keys(where, data, TOP_KEYS)
    for key in ("title", "cards", "steps"):
        if key not in data:
            raise ScenarioError(f"{where}: 必須キー {key!r} がありません")
    overrides = data.get("overrides", {})
    for name, values in overrides.items():
        _check_keys(f"{where} [overrides.{name}]", values, OVERRIDE_KEYS)

    steps = []
    for i, raw in enumerate(data["steps"], start=1):
        _check_keys(f"{where} step {i}", raw, STEP_KEYS)
        _check_keys(f"{where} step {i} expect", raw.get("expect", {}), STEP_EXPECT_KEYS)
        if not raw.get("card") and raw.get("slot") is None:
            raise ScenarioError(f"{where} step {i}: card か slot のどちらかが必要です")
        steps.append(Step(**raw))
    _check_keys(f"{where} [expect]", data.get("expect", {}), FINAL_EXPECT_KEYS)

    return Scenario(
        path=path,
        title=data["title"],
        cards=list(data["cards"]),
        steps=steps,
        hand_size=data.get("hand_size", 3),
        env=dict(data.get("env", {})),
        overrides=overrides,
        description=data.get("description", ""),
        rough_tl=data.get("rough_tl", ""),
        verified=data.get("verified"),
        expect=data.get("expect", {}),
    )


def scenario_paths(directory: Path = SCENARIO_DIR) -> List[Path]:
    return sorted(directory.rglob("*.toml"))


# ---------------------------------------------------------------------------
# Specの構築
# ---------------------------------------------------------------------------


def build_specs(scenario: Scenario) -> List[CharacterSpec]:
    """overrides の cost / extra_cost / role を反映して Spec を組み立てる。"""
    roles = {
        name: o["role"] for name, o in scenario.overrides.items() if "role" in o
    }
    specs: List[CharacterSpec] = []
    for name in dict.fromkeys(scenario.cards):
        o = scenario.overrides.get(name, {})
        spec_cls = CUSTOM_SPECS.get(name)
        if spec_cls is None:
            specs.append(GenericSpec(name, cost=o.get("cost")))
        elif spec_cls is IbukiSwimsuitSpec:
            specs.append(
                IbukiSwimsuitSpec(
                    character_roles=roles, cost=o.get("cost"), extra_cost=o.get("extra_cost")
                )
            )
        else:
            specs.append(spec_cls(cost=o.get("cost")))
    if "Rio" in scenario.cards:
        specs.append(RioCopySpec())
    return specs


# ---------------------------------------------------------------------------
# 期待値の照合
# ---------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    # envのタプル(イブキのお友達等)はTOMLの配列と比較できるようリストにする
    return list(value) if isinstance(value, tuple) else value


def state_dict(state: State) -> Dict[str, Any]:
    return {
        "cards": list(state.cards),
        "hand": list(state.hand),
        "deck": list(state.deck),
        "env": {k: _plain(v) for k, v in state.env.items()},
    }


def check_state(ctx: str, expect: Dict[str, Any], actual: Dict[str, Any]) -> None:
    """cards/hand/deck/hand_excludes/env/env_none を照合する(書かれた項目だけ)。"""
    for key in ("cards", "hand", "deck"):
        if key in expect:
            assert actual[key] == expect[key], (
                f"{ctx}: {key} が違います\n  期待: {expect[key]}\n  実際: {actual[key]}"
            )
    for card in expect.get("hand_excludes", []):
        assert card not in actual["hand"], f"{ctx}: {card} は手札にいないはずです: {actual['hand']}"
    for key, value in expect.get("env", {}).items():
        got = actual["env"].get(key)
        assert got == value, f"{ctx}: env.{key} が違います (期待: {value!r}, 実際: {got!r})"
    for key in expect.get("env_none", []):
        got = actual["env"].get(key)
        assert got is None, f"{ctx}: env.{key} は未設定(None)のはずが {got!r} です"


def check_cost(ctx: str, expect: Dict[str, Any], cost: Optional[int]) -> None:
    if "cost" in expect:
        assert cost == expect["cost"], f"{ctx}: cost が違います (期待: {expect['cost']}, 実際: {cost})"
    if expect.get("cost_unknown"):
        assert cost is None, f"{ctx}: cost は不明(None)のはずが {cost} です"


def _origin(sim: Simulator, card: str) -> str:
    # 代理カード(Rio_Copy)は破棄時の変身先(Rio)に戻して、カード構成の不変条件を比べる
    spec = sim.registry.get(card)
    if spec and spec.is_proxy:
        return spec.get_discard_transform(sim.state) or card
    return card


def check_invariants(ctx: str, sim: Simulator, initial: List[str]) -> None:
    cards = sim.state.cards
    assert None not in cards, f"{ctx}: カードに穴(None)が残っています: {cards}"
    assert sorted(_origin(sim, c) for c in cards) == sorted(initial), (
        f"{ctx}: カード構成が初期から変わりました(消失・重複)\n  初期: {initial}\n  現在: {list(cards)}"
    )


# ---------------------------------------------------------------------------
# 実行(エンジン直結)
# ---------------------------------------------------------------------------


def run_engine(scenario: Scenario) -> Simulator:
    """シナリオを Simulator で実行し、各ステップの期待値と不変条件を検査する。

    card だけのステップは Simulator.play_by_name、slot のステップは Simulator.play を呼ぶ。
    コストは使用前の状態で評価する(webui の /play と同じ規約)。
    """
    sim = Simulator(build_specs(scenario))
    sim.initialize_state(
        tuple(scenario.cards), env=dict(scenario.env), hand_size=scenario.hand_size
    )
    total_cost = 0

    for i, step in enumerate(scenario.steps, start=1):
        ctx = f"{scenario.id} step {i}" + (f" ({step.note})" if step.note else "")
        expect = step.expect

        if step.slot is not None:
            card = sim.state.hand[step.slot]
            if step.card:
                assert card == step.card, f"{ctx}: スロット{step.slot}は {card} で、{step.card} ではありません"
        else:
            card = step.card
        cost = sim.registry.evaluate_cost(sim.state, card)

        try:
            if step.slot is not None:
                sim.play(step.slot, target=step.target)
            else:
                sim.play_by_name(step.card, target=step.target)
        except Exception as e:
            if "error" not in expect:
                raise AssertionError(f"{ctx}: 予期しない例外 {e!r}") from e
            assert type(e).__name__ == expect["error"], (
                f"{ctx}: {expect['error']} を期待しましたが {type(e).__name__} でした: {e}"
            )
            assert expect.get("error_match", "") in str(e), (
                f"{ctx}: 例外メッセージに {expect['error_match']!r} が含まれません: {e}"
            )
            continue
        if "error" in expect:
            raise AssertionError(f"{ctx}: {expect['error']} を期待しましたが成功しました")

        total_cost += cost or 0
        check_cost(ctx, expect, cost)
        check_state(ctx, expect, state_dict(sim.state))
        check_invariants(ctx, sim, scenario.cards)

    final = scenario.expect
    check_state(f"{scenario.id} 最終状態", final, state_dict(sim.state))
    if "total_cost" in final:
        assert total_cost == final["total_cost"], (
            f"{scenario.id}: 累計コストが違います (期待: {final['total_cost']}, 実際: {total_cost})"
        )
    return sim
