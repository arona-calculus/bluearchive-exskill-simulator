from __future__ import annotations
from ba_exsim.core.compiler import TimelineCompiler
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec


def test_rio_hanako_integration():
    """
    リオと水着ハナコの相互作用をテストする。
    - リオがハナコを対象にEXを使用した場合、リオはアバンギャルドに変身する。
    - アバンギャルドがハナコを代理実行しても、ハナコ自身のゲージは消費されない。
    - アバンギャルドがハナコを代理実行しても、ハナコのゲージは増加しない。
    - アバンギャルドが消費された後、リオがデッキに帰還する。
    """
    # --- Setup ---
    specs = [
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Kisaki"),
        GenericSpec("Kikyo"),
        GenericSpec("Sena"),
        RioCopySpec(),
    ]
    initial_cards = ("Rio", "Hanako", "Aru", "Kisaki", "Kikyo", "Sena", "Rio_Copy")

    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state_0 = compiler.build_initial_state(initial_cards).update(L=6)

    # --- Initial State ---
    assert state_0.cards == ("Rio", "Hanako", "Aru", "Kisaki", "Kikyo", "Sena", "Rio_Copy")
    assert state_0.get_env("hanako_gauge", 0) == 0
    print("\n[OK] 初期状態")

    # --- Step 1: Aru EX (slot 2) ---
    state_1 = transition(state_0, 2)
    assert state_1.cards == ("Rio", "Hanako", "Kisaki", "Kikyo", "Sena", "Aru", "Rio_Copy")
    assert state_1.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 1: Aru使用でハナコのゲージが+40")

    # --- Step 2: Rio EX -> 対象: Hanako (slot 0) ---
    state_2 = transition(state_1, 0, target="Hanako")
    assert state_2.cards == ("Rio_Copy", "Hanako", "Kisaki", "Kikyo", "Sena", "Aru", "Rio")
    assert state_2.env.get("rio_copy_target") == "Hanako"
    assert state_2.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 2: リオがハナコを対象に使用し、Rio_copyに変身。ゲージは+40され80に。")

    # --- Step 3: Rio_Copy EX (slot 0) ---
    state_3 = transition(state_2, 0)
    assert state_3.cards == ("Kikyo", "Hanako", "Kisaki", "Sena", "Aru", "Rio", "Rio_Copy")
    assert "rio_parked_index" not in state_3.env
    assert state_3.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 3: Rio_copyがハナコを代理実行。正常にサイクルし、リオが帰還。代理実行ではゲージは増減せず80のまま。")

    # --- Step 4: Kikyo EX (slot 0) ---
    state_4 = transition(state_3, 0)
    assert state_4.cards == ("Sena", "Hanako", "Kisaki", "Aru", "Rio", "Kikyo", "Rio_Copy")
    assert state_4.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 4: Kikyo使用でハナコのゲージが120")

    # --- Step 5: Sena EX (slot 0) ---
    state_5 = transition(state_4, 0)
    assert state_5.cards == ("Aru", "Hanako", "Kisaki", "Rio", "Kikyo", "Sena", "Rio_Copy")
    assert state_5.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 5: Sena使用でハナコのゲージが160")

    # --- Step 6: Hanako EX (slot 1) ---
    state_6 = transition(state_5, 1)
    assert state_6.cards == ("Aru", "Hanako", "Kisaki", "Rio", "Kikyo", "Sena", "Rio_Copy")
    assert state_6.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 6: ハナコ自身がEXを使用。ゲージを100消費し、手札に留まる。")


if __name__ == "__main__":
    test_rio_hanako_integration()
