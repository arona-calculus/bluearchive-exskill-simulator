from __future__ import annotations
from ba_exsim.core.compiler import TimelineCompiler
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec


def test_rio_hanako_integration():
    """
    リオと水着ハナコの相互作用をテストする（test_rio_hanako.py とは異なる初期デッキ）。
    - リオがハナコを対象にEXを使用した場合、リオはアバンギャルドに変身する。
    - アバンギャルドがハナコを代理実行しても、ハナコ自身のゲージは消費も増加もしない。
    - アバンギャルドが消費された後、リオがデッキに帰還する。
    - ハナコはゲージを消費して手札に留まることができる。
    """
    # --- 1. Setup ---
    specs = [
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Kisaki"),
        GenericSpec("Kikyo"),
        GenericSpec("Sena"),
        RioCopySpec(),
    ]
    initial_cards = ("Hanako", "Sena", "Kikyo", "Aru", "Rio", "Kisaki", "Rio_Copy")

    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state_0 = compiler.build_initial_state(initial_cards).update(L=6)

    # --- Initial State ---
    assert state_0.cards == ("Hanako", "Sena", "Kikyo", "Aru", "Rio", "Kisaki", "Rio_Copy")
    assert state_0.get_env("hanako_gauge", 0) == 0
    print("\n[OK] 初期状態")

    # --- Step 1: Sena EX (slot 1) ---
    state_1 = transition(state_0, 1)
    assert state_1.cards == ("Hanako", "Aru", "Kikyo", "Rio", "Kisaki", "Sena", "Rio_Copy")
    assert state_1.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 1: Sena使用でハナコのゲージが+40")

    # --- Step 2: Hanako EX (slot 0) ---
    state_2 = transition(state_1, 0)
    assert state_2.cards == ("Rio", "Aru", "Kikyo", "Kisaki", "Sena", "Hanako", "Rio_Copy")
    assert state_2.get_env("hanako_gauge", 0) == 40  # ゲージ不足(40)なので通常サイクル
    print("[OK] Step 2: ハナコがゲージ不足で通常サイクル")

    # --- Step 3: Aru EX (slot 1) ---
    state_3 = transition(state_2, 1)
    assert state_3.cards == ("Rio", "Kisaki", "Kikyo", "Sena", "Hanako", "Aru", "Rio_Copy")
    assert state_3.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 3: Aru使用でハナコのゲージが80")

    # --- Step 4: Kisaki EX (slot 1) ---
    state_4 = transition(state_3, 1)
    assert state_4.cards == ("Rio", "Sena", "Kikyo", "Hanako", "Aru", "Kisaki", "Rio_Copy")
    assert state_4.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 4: Kisaki使用でハナコのゲージが120")

    # --- Step 5: Sena EX (slot 1) ---
    state_5 = transition(state_4, 1)
    assert state_5.cards == ("Rio", "Hanako", "Kikyo", "Aru", "Kisaki", "Sena", "Rio_Copy")
    assert state_5.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 5: Sena使用でハナコのゲージが160")

    # --- Step 6: Rio EX -> 対象: Hanako (slot 0) ---
    state_6 = transition(state_5, 0, target="Hanako")
    assert state_6.cards == ("Rio_Copy", "Hanako", "Kikyo", "Aru", "Kisaki", "Sena", "Rio")
    assert state_6.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 6: リオがハナコを対象に使用し、Rio_copyに変身。ゲージは200(Max)に。")

    # --- Step 7: Rio_Copy EX (slot 0) ---
    state_7 = transition(state_6, 0)
    assert state_7.cards == ("Kikyo", "Hanako", "Aru", "Kisaki", "Sena", "Rio", "Rio_Copy")
    assert state_7.get_env("hanako_gauge", 0) == 200  # 代理実行なのでゲージは増減しない
    print("[OK] Step 7: Rio_copyがハナコを代理実行。ゲージは200のまま。")

    # --- Step 8: Hanako EX (slot 1) ---
    state_8 = transition(state_7, 1)
    assert state_8.cards == ("Kikyo", "Hanako", "Aru", "Kisaki", "Sena", "Rio", "Rio_Copy")
    assert state_8.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 8: ハナコがEXを使用。ゲージを100消費し手札に留まる。")

    # --- Step 9: Hanako EX (slot 1) ---
    state_9 = transition(state_8, 1)
    assert state_9.cards == ("Kikyo", "Hanako", "Aru", "Kisaki", "Sena", "Rio", "Rio_Copy")
    assert state_9.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 9: ハナコが再度EXを使用。ゲージを100消費し手札に留まる。")

    # --- Step 10: Hanako EX (slot 1) ---
    state_10 = transition(state_9, 1)
    assert state_10.cards == ("Kikyo", "Aru", "Kisaki", "Sena", "Rio", "Hanako", "Rio_Copy")
    assert state_10.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 10: ハナコがゲージ0でEXを使用。通常通りサイクルする。")
