from __future__ import annotations
from ba_exsim.core.compiler import TimelineCompiler
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.alice_battle import AliceBattleSpec


def test_alice_battle_behavior():
    """
    アリス（臨戦）の単体仕様をテストする。
    - 自身を対象にEXを使用するとチャージが増加し、手札に留まること。
    - 敵を対象にEXを使用するとチャージがリセットされ、通常通りサイクルすること。
    - チャージには上限があること。
    """
    # --- 1. セットアップ ---
    specs = [
        AliceBattleSpec(),
        GenericSpec("Aru"),
        GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"),
    ]
    initial_cards = ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state = compiler.build_initial_state(initial_cards)

    # --- 初期状態の確認 ---
    assert state.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state.get_env("alice_charge", 0) == 0
    print("\n[OK] 初期状態は正常です。")

    # --- Step 1: 自身を対象にEXを使用（チャージ1） ---
    # チャージが1増加し、手札に留まる
    state_1 = transition(state, 0, target="Alice_Battle")
    assert state_1.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state_1.get_env("alice_charge") == 1
    print(f"[OK] Step 1: 自身を対象に使用し、チャージが {state_1.get_env('alice_charge')} になりました。")

    # --- Step 2: 自身を対象にEXを使用（チャージ2, 上限） ---
    # チャージが2に増加し、手札に留まる
    state_2 = transition(state_1, 0, target="Alice_Battle")
    assert state_2.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state_2.get_env("alice_charge") == 2
    print(f"[OK] Step 2: 自身を対象に使用し、チャージが {state_2.get_env('alice_charge')} になりました。")

    # --- Step 3: 上限の状態で自身を対象にEXを使用 ---
    # チャージは上限(2)のままで、手札に留まる
    state_3 = transition(state_2, 0, target="Alice_Battle")
    assert state_3.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state_3.get_env("alice_charge") == 2
    print(f"[OK] Step 3: チャージが上限 {state_3.get_env('alice_charge')} のまま維持されることを確認しました。")

    # --- Step 4: 敵を対象にEXを使用 ---
    # チャージがリセット(0)され、通常通り山札の最後尾に移動する
    state_4 = transition(state_3, 0, target="Enemy")
    assert state_4.cards == ("Kayoko", "Aru", "Mutsuki", "Alice_Battle")
    assert state_4.get_env("alice_charge") == 0
    print("[OK] Step 4: 敵を対象に使用し、正常にサイクルしチャージがリセットされました。")

    # --- Step 5: チャージ0の状態で敵を対象にEXを使用 ---
    # 通常通りサイクルし、チャージは0のまま
    # まず、他のカードを使ってアリスを手札に戻す
    state_5 = transition(state_4, 0)  # Kayokoを使用

    assert state_5.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")

    # アリスEXをチャージ0で打つ
    state_6 = transition(state_5, 0, target="Enemy")
    assert state_6.cards == ("Kayoko", "Aru", "Mutsuki", "Alice_Battle")
    assert state_6.get_env("alice_charge") == 0
    print("[OK] Step 5: チャージ0の状態で正常にサイクルすることを確認しました。")
