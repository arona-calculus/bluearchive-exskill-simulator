from __future__ import annotations
from ba_exsim.core.simulator import Simulator
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

    # 新アーキテクチャ: Simulatorで複雑な配線を隠蔽
    sim = Simulator(specs)

    # 初期状態: アリスのチャージは0
    initial_cards = ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    state = sim.initialize_state(initial_cards, env={"alice_charge": 0})

    # --- 初期状態の確認 ---
    assert state.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state.get_env("alice_charge", 0) == 0
    print("\n[OK] 初期状態は正常です。")

    # --- Step 1: 自身を対象にEXを使用（チャージ1） ---
    # チャージが1増加し、手札に留まる
    state = sim.play(0, target="Alice_Battle")
    print(state.cards)
    assert state.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state.get_env("alice_charge") == 1
    print(f"[OK] Step 1: 自身を対象に使用し、チャージが {state.get_env('alice_charge')} になりました。")

    # --- Step 2: 自身を対象にEXを使用（チャージ2, 上限） ---
    # チャージが2に増加し、手札に留まる
    state = sim.play(0, target="Alice_Battle")
    assert state.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state.get_env("alice_charge") == 2
    print(f"[OK] Step 2: 自身を対象に使用し、チャージが {state.get_env('alice_charge')} になりました。")

    # --- Step 3: 上限の状態で自身を対象にEXを使用 ---
    # チャージは上限(2)のままで、手札に留まる
    state = sim.play(0, target="Alice_Battle")
    assert state.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")
    assert state.get_env("alice_charge") == 2
    print(f"[OK] Step 3: チャージが上限 {state.get_env('alice_charge')} のまま維持されることを確認しました。")

    # --- Step 4: 敵を対象にEXを使用 ---
    # チャージがリセット(0)され、通常通り山札の最後尾に移動する
    state = sim.play(0, target="Enemy")
    assert state.cards == ("Kayoko", "Aru", "Mutsuki", "Alice_Battle")
    assert state.get_env("alice_charge") == 0
    print("[OK] Step 4: 敵を対象に使用し、正常にサイクルしチャージがリセットされました。")

    # --- Step 5: チャージ0の状態で敵を対象にEXを使用 ---
    # 通常通りサイクルし、チャージは0のまま
    # まず、他のカードを使ってアリスを手札に戻す
    state = sim.play(0)  # Kayokoを使用
    assert state.cards == ("Alice_Battle", "Aru", "Mutsuki", "Kayoko")

    # アリスEXをチャージ0で打つ
    state = sim.play(0, target="Enemy")
    assert state.cards == ("Kayoko", "Aru", "Mutsuki", "Alice_Battle")
    assert state.get_env("alice_charge") == 0
    print("[OK] Step 5: チャージ0の状態で正常にサイクルすることを確認しました。")


if __name__ == "__main__":
    test_alice_battle_behavior()
