from __future__ import annotations
from ba_exsim.core.state import State
from ba_exsim.core.compiler import TimelineCompiler, CharacterSpec
from ba_exsim.specs.rio import RioSpec, AvantGardeSpec
from ba_exsim.specs.generic import GenericSpec


# --- テストケース ---
def test_rio_basic_copy():
    """
    ケース1: 通常のキャラクター（Aru）をコピーした場合のテスト
    """
    print("=== Test Case 1: Basic Copy (Aru) ===")
    specs = [
        RioSpec(), GenericSpec("Aru"), GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"), GenericSpec("Haruka"), GenericSpec("Hoshino"),
        AvantGardeSpec()
    ]
    initial_cards = ("Rio", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino", "AvantGarde")
    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state_0 = compiler.build_initial_state(initial_cards).update(L=6)

    # Step 1: リオがAruを対象にEXを使用
    state_1 = transition(state_0, 0, target="Aru")
    assert state_1.cards == ("AvantGarde", "Aru", "Mutsuki", "Kayoko", "Haruka", "Hoshino", "Rio")
    assert state_1.env.get("avant_garde_copied_target") == "Aru"
    print("[OK] Step 1: リオが即座にAvantGardeに変身（コピー対象: Aru）。デッキは回らない。")

    # Step 2: AvantGardeを使用（ターゲットは敵を想定）
    state_2 = transition(state_1, 0, target="Enemy")
    # Aruの仕様（通常サイクル）が代理実行され、AvantGardeが消費されるため、リオが最後尾に帰還する
    assert state_2.cards == ("Kayoko", "Aru", "Mutsuki", "Haruka", "Hoshino", "Rio", "AvantGarde")
    assert "rio_parked_index" not in state_2.env
    print("[OK] Step 2: AvantGarde使用。Aruの仕様が代理実行され、リオが最後尾に帰還した。\n")


if __name__ == "__main__":
    test_rio_basic_copy()
