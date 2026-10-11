from __future__ import annotations

from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.ibuki_swimsuit import IbukiSwimsuitSpec
from ba_exsim.specs.rio import RioCopySpec, RioSpec


def test_generic_spec_returns_static_cost():
    """GenericSpecは渡されたコストをそのまま返す(未指定ならNone)。"""
    spec_with_cost = GenericSpec("Aru", cost=4)
    spec_without_cost = GenericSpec("Eri")

    state = Simulator([spec_with_cost]).initialize_state(("Aru",))
    assert spec_with_cost.get_cost(state) == 4
    assert spec_without_cost.get_cost(state) is None


def test_rio_copy_cost_is_target_cost_minus_one():
    """
    リオ(コピー)の消費コストは「コピー元(対象)のコスト - 1」(最低0)になること。
    rio_copy_targetはRioCopySpec.apply_effect自身がクリアするため、
    get_costはプレイ前のstateに対して呼ぶ必要がある(= main.pyでのstate_before相当)。
    """
    specs = [
        RioSpec(cost=2),
        RioCopySpec(),
        GenericSpec("Aru", cost=4),
        GenericSpec("Eri", cost=1),  # cost-1が0未満にならないケースの確認用
        GenericSpec("Kisaki"),  # cost不明のキャラをコピーした場合の確認用
    ]
    initial_cards = ("Rio", "Aru", "Eri", "Kisaki")
    sim = Simulator(specs)
    sim.initialize_state(initial_cards)

    rio_copy_spec = sim.registry.get("Rio_Copy")

    # Aru(コスト4)をコピー → 4-1=3
    state = sim.play_by_name("Rio", target="Aru")
    assert rio_copy_spec.get_cost(state) == 3

    # Eri(コスト1)をコピー → 1-1=0 (負にならない)
    state2 = Simulator(specs)
    state2.initialize_state(initial_cards)
    state_after = state2.play_by_name("Rio", target="Eri")
    assert rio_copy_spec.get_cost(state_after) == 0

    # コスト不明のキャラ(Kisaki)をコピー → None
    state3 = Simulator(specs)
    state3.initialize_state(initial_cards)
    state_after3 = state3.play_by_name("Rio", target="Kisaki")
    assert rio_copy_spec.get_cost(state_after3) is None


def test_ibuki_swimsuit_cost_switches_between_ex1_and_ex2():
    """
    イブキ(水着)はお友達未指定時(EX1)はcost、指定済み(EX2)はextra_costを返すこと。
    """
    ibuki = IbukiSwimsuitSpec(
        character_roles={"Aru": "STRIKER", "Eri": "STRIKER"}, cost=0, extra_cost=3,
    )
    specs = [ibuki, GenericSpec("Aru"), GenericSpec("Eri"), GenericSpec("Kisaki")]
    initial_cards = ("Ibuki_Swimsuit", "Aru", "Eri", "Kisaki")
    sim = Simulator(specs)
    state = sim.initialize_state(initial_cards)

    # EX1(未指定): cost=0
    assert ibuki.get_cost(state) == 0

    state_after_ex1 = sim.play_by_name("Ibuki_Swimsuit", target="Aru,Eri")
    # EX2(指定済み): extra_cost=3
    assert ibuki.get_cost(state_after_ex1) == 3
