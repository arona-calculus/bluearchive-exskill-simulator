from __future__ import annotations
from ba_exsim.core.state import State
from ba_exsim.core.compiler import TimelineCompiler, CharacterSpec
from ba_exsim.specs.rio import RioSpec, AvantGardeSpec
from ba_exsim.specs.alice_battle import AliceBattleSpec
from ba_exsim.specs.generic import GenericSpec


# --- テストケース ---
def test_rio_conditional_copy():
    """
    ケース2: 条件で手札に留まるキャラクター（Alice_Battle）をコピーした場合のテスト
    """
    print("=== Test Case 2: Conditional Copy (Alice_Battle) ===")
    specs = [
        RioSpec(), AliceBattleSpec(), GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"), GenericSpec("Haruka"), GenericSpec("Hoshino"),
        AvantGardeSpec()
    ]
    initial_cards = ("Rio", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino", "AvantGarde")
    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state_0 = compiler.build_initial_state(initial_cards).update(L=6)

    # Step 1: リオがAlice_Battleを対象にEXを使用
    state_1 = transition(state_0, 0, target="Alice_Battle")
    assert state_1.cards == ("AvantGarde", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino", "Rio")
    print("[OK] Step 1: リオがAvantGardeに変身（コピー対象: Alice_Battle）。")

    # Step 2: AvantGardeが「自身(AvantGarde)」を対象にEXを使用
    # アリスの仕様上、自分自身を対象にするとチャージが貯まり、手札に留まるはず。
    state_2 = transition(state_1, 0, target="AvantGarde")

    # 検証: AvantGardeはスロット0に留まっており、リオも帰還していない。チャージが+1されている。
    assert state_2.cards[0] == "AvantGarde"
    assert state_2.cards == ("AvantGarde", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino", "Rio")
    assert state_2.env.get("alice_charge") == 1
    assert state_2.env.get("rio_parked_index") == 6
    print("[OK] Step 2: AvantGardeが自身を対象に使用。アリスの仕様が代理実行され、手札に留まった！（リオは帰還せず）")

    # Step 3: AvantGardeが「敵(Enemy)」を対象にEXを使用
    # アリスの仕様上、敵を対象にするとサイクルが発生するはず。
    state_3 = transition(state_2, 0, target="Enemy")

    # 検証: サイクルが発生し、ここで初めてリオが最後尾(idx 5)に帰還する。
    assert state_3.cards == ("Kayoko", "Alice_Battle", "Mutsuki", "Haruka", "Hoshino", "Rio", "AvantGarde")
    assert state_3.env.get("alice_charge") == 0
    assert "rio_parked_index" not in state_3.env
    print("[OK] Step 3: AvantGardeが敵を対象に使用。サイクルが発生し、リオが最後尾に帰還した！")


if __name__ == "__main__":
    test_rio_conditional_copy()
