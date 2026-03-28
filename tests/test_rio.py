from __future__ import annotations
from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.rio import RioSpec, RioCopySpec
from ba_exsim.specs.generic import GenericSpec


# --- テストケース ---
def test_rio_basic_copy():
    """
    ケース1: 通常のキャラクター（Aru）をコピーした場合のテスト
    - Rio -> Rio_Copyへの変身
    - Rio_Copyがサイクル（消費）された後、Rioに戻る
    """
    print("=== Test Case 1: Basic Copy (Aru) ===")
    specs = [
        RioSpec(),
        GenericSpec("Aru"),
        GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"),
        RioCopySpec()
    ]
    # Rio_Copyは事前にデッキに存在する必要がある
    initial_cards = ("Rio", "Aru", "Mutsuki", "Kayoko")

    sim = Simulator(specs)
    state_0 = sim.initialize_state(initial_cards)
    assert state_0.cards == ("Rio", "Aru", "Mutsuki", "Kayoko")
    print("[OK] 初期状態")

    # Step 1: リオがAruを対象にEXを使用
    # Hand: ("Rio", "Aru", "Mutsuki"), Deck: ("Kayoko")
    state_1 = sim.play_by_name("Rio", target="Aru")
    assert state_1.cards == ("Rio_Copy", "Aru", "Mutsuki", "Kayoko")
    assert state_1.env.get("rio_copy_target") == "Aru"
    print("[OK] Step 1: リオが即座にRio_copyに変身（コピー対象: Aru）。")

    # Step 2: Rio_copyを使用
    # Hand: ("Rio_Copy", "Aru", "Mutsuki"), Deck: ("Kayoko", "Rio")
    state_2 = sim.play_by_name("Rio_Copy")
    assert state_2.cards == ("Kayoko", "Aru", "Mutsuki", "Rio")
    assert state_2.env.get("rio_copy_target") is None
    print("[OK] Step 2: Rio_copy使用。サイクルしてRioに戻り、デッキに正しく追加された。\n")
