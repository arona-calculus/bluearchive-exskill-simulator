from __future__ import annotations
from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec


def test_rio_hanako_integration():
    """
    リオと水着ハナコの相互作用をテストする。
    - リオがハナコを対象にEXを使用した場合、Rio_Copyに変身する。
    - Rio_CopyがハナコEXを代理実行しても、ハナコが手札にいる場合はゲージ消費・増減なし。
    - Rio_CopyがハナコEXを代理実行後、正常にサイクルしリオが山札末尾に帰還する。
    - ハナコ本人はゲージ100以上でEXを使用するとゲージを消費して手札に留まる。
    """
    # --- Setup ---
    specs = [
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Kisaki"),
        GenericSpec("Kikyou"),
        GenericSpec("Sena"),
        RioCopySpec(),
    ]
    initial_cards = ("Rio", "Hanako", "Aru", "Kisaki", "Kikyou", "Sena")

    sim = Simulator(specs)
    state = sim.initialize_state(initial_cards)

    # --- Initial State ---
    assert state.cards == ("Rio", "Hanako", "Aru", "Kisaki", "Kikyou", "Sena")
    assert state.get_env("hanako_gauge", 0) == 0
    print("\n[OK] 初期状態")

    # --- Step 1: Aru EX (slot 2) ---
    # パッシブによりハナコのゲージが+40。
    state = sim.play(2)
    assert state.cards == ("Rio", "Hanako", "Kisaki", "Kikyou", "Sena", "Aru")
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 1: Aru使用でハナコのゲージが+40（40）。")

    # --- Step 2: Rio EX -> 対象: Hanako (slot 0) ---
    # リオはis_proxy=Falseのためパッシブによりハナコのゲージがさらに+40。
    # リオはその場でRio_Copyに変身し、rio_copy_target="Hanako"を記録する。
    state = sim.play(0, target="Hanako")
    assert state.cards == ("Rio_Copy", "Hanako", "Kisaki", "Kikyou", "Sena", "Aru")
    assert state.get_env("rio_copy_target") == "Hanako"
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 2: リオがハナコを対象に使用しRio_Copyに変身。パッシブでゲージ+40（80）。")

    # --- Step 3: Rio_Copy EX (slot 0) ---
    # ハナコが手札にいる（スロット1）かつゲージ80<100のため、
    # ハナコのapply_effectは何もしない。ゲージ増減なし。
    # Rio_CopyはRioに変身して山札末尾へ帰還。
    state = sim.play(0)
    assert state.cards == ("Kikyou", "Hanako", "Kisaki", "Sena", "Aru", "Rio")
    assert state.get_env("rio_copy_target") is None
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 3: Rio_CopyがハナコEXを代理実行。ゲージ増減なし（80）。リオが山札末尾に帰還。")

    # --- Step 4: Kikyou EX (slot 2) ---
    # パッシブによりハナコのゲージが+40。
    state = sim.play(0)
    assert state.cards == ("Sena", "Hanako", "Kisaki", "Aru", "Rio", "Kikyou")
    assert state.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 4: Kikyo使用でハナコのゲージが+40（120）。")

    # --- Step 5: Sena EX (slot 2) ---
    # パッシブによりハナコのゲージが+40。
    state = sim.play(0)
    assert state.cards == ("Aru", "Hanako", "Kisaki", "Rio", "Kikyou", "Sena")
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 5: Sena使用でハナコのゲージが+40（160）。")

    # --- Step 6: Hanako EX (slot 1) ---
    # ゲージ160≥100のため、ゲージを100消費して手札に留まる。
    state = sim.play(1)
    assert state.cards == ("Aru", "Hanako", "Kisaki", "Rio", "Kikyou", "Sena")
    assert state.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 6: ハナコ自身がEXを使用。ゲージを100消費して手札に留まる（60）。")

    # --- Step 7: Hanako EX (slot 1) ---
    # ゲージ60<100のため、通常サイクル。
    state = sim.play(1)
    assert state.cards == ("Aru", "Rio", "Kisaki", "Kikyou", "Sena", "Hanako")
    assert state.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 6: ハナコ自身がEXを使用。ゲージを100消費して手札に留まる（60）。")


if __name__ == "__main__":
    test_rio_hanako_integration()
