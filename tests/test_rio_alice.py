from __future__ import annotations
from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec
from ba_exsim.specs.alice_battle import AliceBattleSpec


def test_rio_alice_battle():
    """
    ケース2: 条件で手札に留まるキャラクター（Alice_Battle）をコピーした場合のテスト
    """
    print("\n=== Test Case 2: Conditional Copy (Alice_Battle) ===")

    specs = [
        RioSpec(), AliceBattleSpec(), GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"), GenericSpec("Haruka"), GenericSpec("Hoshino"),
        RioCopySpec()
    ]
    sim = Simulator(specs)

    initial_cards = ("Rio", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    state = sim.initialize_state(initial_cards, env={"alice_charge": 0})

    # Step 1: リオがAlice_Battleを対象にEXを使用
    # リオがその場で "Rio_Copy" に変身し、ターゲット情報を環境変数に記録する
    # should_cycle=False のためサイクルなし、パッシブのみ走る
    state = sim.play(0, target="Alice_Battle")
    assert state.cards == ("Rio_Copy", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state.get_env("rio_copy_target") == "Alice_Battle"
    assert state.get_env("alice_charge") == 0
    print("[OK] Step 1: リオがRio_Copyに変身（コピー対象: Alice_Battle）。")

    # Step 2: Rio_Copyがアリスのチャージを使用
    # アリスの should_cycle は target == active_card で判定する。
    # active_card は "Rio_Copy" なので、target="Rio_Copy" で自身対象となる。
    # → チャージ+1、should_cycle=False → 手札に留まる（サイクルなし）
    state = sim.play(0, target="Alice_Battle")
    assert state.cards == ("Kayoko", "Alice_Battle", "Mutsuki", "Haruka", "Hoshino", "Rio")
    assert state.get_env("alice_charge") == 1
    print("[OK] Step 2: Rio_Copyが自身を対象に使用。チャージ+1、手札に留まる。")

    # Step 3: Rio_Copyが「敵(Enemy)」を対象にEXを使用
    # アリスの should_cycle は target != active_card → True → サイクル発生
    # apply_effect: alice_charge → 0（消費）
    # get_discard_transform: "Rio" に変身して山札末尾へ
    # 山札末尾から先頭（スロット0）へドロー → Kayokoが来る
    state = sim.play(1, target="Enemy")
    assert state.cards == ("Kayoko", "Haruka", "Mutsuki", "Hoshino", "Rio", "Alice_Battle")
    assert state.get_env("alice_charge") == 0
    assert state.get_env("rio_copy_target") is None
    print("[OK] Step 3: Rio_Copyが敵を対象に使用。サイクル発生、リオが山札末尾に帰還。")


def test_alice_direct_self_target():
    """
    ケース: アリスとリオが同時に手札にある状態で、
    アリス本人が自身（Alice_Battle）を対象にEXを使用する。
    リオの存在がアリスの挙動に影響しないことを確認する。
    """
    print("\n=== Test: Alice direct self-target with Rio in hand ===")

    specs = [
        RioSpec(), AliceBattleSpec(), GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"), GenericSpec("Haruka"), GenericSpec("Hoshino"),
        RioCopySpec()
    ]
    sim = Simulator(specs)

    initial_cards = ("Alice_Battle", "Rio", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    state = sim.initialize_state(initial_cards, env={"alice_charge": 0})

    # Step 1: アリスが自身を対象にEXを使用
    # → チャージ+1、should_cycle=False → 手札に留まる
    state = sim.play(0, target="Alice_Battle")
    assert state.cards == ("Alice_Battle", "Rio", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state.get_env("alice_charge") == 1
    print("[OK] Step 1: アリスが自身を対象に使用。チャージ+1、手札に留まる。")

    # Step 2: アリスが再度自身を対象にEXを使用
    # → チャージ+1（上限2）、手札に留まる
    state = sim.play(0, target="Alice_Battle")
    assert state.cards == ("Alice_Battle", "Rio", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state.get_env("alice_charge") == 2
    print("[OK] Step 2: アリスが再度自身を対象に使用。チャージ+1（上限2）、手札に留まる。")

    # Step 3: アリスが敵を対象にEXを使用
    # → チャージ消費（リセット）、should_cycle=True → 通常サイクル
    state = sim.play(0, target="Enemy")
    assert state.cards == ("Kayoko", "Rio", "Mutsuki", "Haruka", "Hoshino", "Alice_Battle")
    assert state.get_env("alice_charge") == 0
    print("[OK] Step 3: アリスが敵を対象に使用。チャージ消費、通常サイクル。")


def test_rio_non_alice_target_with_alice_in_hand():
    """
    ケース: アリスとリオが同時に手札にある状態で、
    リオがアリス以外（Mutsuki）を対象にEXを使用する。
    アリスのチャージ状態が一切変化しないことを確認する。
    """
    print("\n=== Test: Rio copies non-Alice target with Alice in hand ===")

    specs = [
        RioSpec(), AliceBattleSpec(), GenericSpec("Mutsuki"),
        GenericSpec("Kayoko"), GenericSpec("Haruka"), GenericSpec("Hoshino"),
        RioCopySpec()
    ]
    sim = Simulator(specs)

    initial_cards = ("Rio", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    state = sim.initialize_state(initial_cards, env={"alice_charge": 1})

    # Step 1: リオがMutsukiを対象にEXを使用
    # → Rio_Copyに変身、アリスのチャージに変化なし
    state = sim.play(0, target="Mutsuki")
    assert state.cards == ("Rio_Copy", "Alice_Battle", "Mutsuki", "Kayoko", "Haruka", "Hoshino")
    assert state.get_env("rio_copy_target") == "Mutsuki"
    assert state.get_env("alice_charge") == 1  # アリスのチャージは変化しない
    print("[OK] Step 1: リオがMutsukiをコピー。アリスのチャージに変化なし。")

    # Step 2: Rio_CopyがMutsukiのEXを代理実行（汎用的な挙動）
    # → 通常サイクル、Rioが山札末尾に帰還、アリスのチャージに変化なし
    state = sim.play(0, target="Enemy")
    assert state.cards == ("Kayoko", "Alice_Battle", "Mutsuki", "Haruka", "Hoshino", "Rio")
    assert state.get_env("alice_charge") == 1  # アリスのチャージは依然変化しない
    assert state.get_env("rio_copy_target") is None
    print("[OK] Step 2: Rio_CopyがMutsukiのEXを代理実行。アリスのチャージに変化なし。")

    # Step 3: アリス本人が自身を対象にEXを使用
    # → チャージ+1（1→2）、手札に留まる
    state = sim.play(1, target="Alice_Battle")
    assert state.cards == ("Kayoko", "Alice_Battle", "Mutsuki", "Haruka", "Hoshino", "Rio")
    assert state.get_env("alice_charge") == 2
    print("[OK] Step 3: アリス本人が自身を対象に使用。チャージ+1（2）、手札に留まる。")