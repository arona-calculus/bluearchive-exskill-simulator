from __future__ import annotations
from ba_exsim.core.compiler import TimelineCompiler
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec


def test_rio_hanako_integration():
    """
    リオと水着ハナコの相互作用をテストする（test_rio_hanako.py とは異なる初期デッキ）
    - リオがハナコを対象にEXを使用した場合、リオはアバンギャルドにコピーする
    - アバンギャルドがハナコを代理実行しても、ハナコ自身のゲージは消費も増加もしない
    - アバンギャルドが消費された後、リオがデッキに帰還する
    - ハナコはゲージを消費して手札に留まることができる
    """
    # --- 1. Setup ---
    specs = [
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Kisaki"),
        GenericSpec("Kikyou"),
        GenericSpec("Sena"),
        RioCopySpec(),
    ]
    initial_cards = ("Hanako", "Sena", "Kikyou", "Aru", "Rio", "Kisaki", "Rio_Copy")

    compiler = TimelineCompiler(specs)
    transition = compiler.compile()
    state_0 = compiler.build_initial_state(initial_cards).update(L=6)

    # --- Initial State ---
    assert state_0.cards == ("Hanako", "Sena", "Kikyou", "Aru", "Rio", "Kisaki", "Rio_Copy")
    assert state_0.get_env("hanako_gauge", 0) == 0
    print("\n[OK] 初期状態")

    # --- Step 1: Sena EX (slot 1) ---
    state_1 = transition(state_0, 1)
    assert state_1.cards == ("Hanako", "Aru", "Kikyou", "Rio", "Kisaki", "Sena", "Rio_Copy")
    assert state_1.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 1: Sena")

    # --- Step 2: Hanako EX (slot 0) ---
    state_2 = transition(state_1, 0)
    assert state_2.cards == ("Rio", "Aru", "Kikyou", "Kisaki", "Sena", "Hanako", "Rio_Copy")
    assert state_2.get_env("hanako_gauge", 0) == 40  # ゲージ不足(40)なので通常サイクル
    print("[OK] Step 2: Hanakoがゲージ不足で通常サイクル")

    # --- Step 3: Aru EX (slot 1) ---
    state_3 = transition(state_2, 1)
    assert state_3.cards == ("Rio", "Kisaki", "Kikyou", "Sena", "Hanako", "Aru", "Rio_Copy")
    assert state_3.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 3: Aru")

    # --- Step 4: Kisaki EX (slot 1) ---
    state_4 = transition(state_3, 1)
    assert state_4.cards == ("Rio", "Sena", "Kikyou", "Hanako", "Aru", "Kisaki", "Rio_Copy")
    assert state_4.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 4: Kisaki")

    # --- Step 5: Sena EX (slot 1) ---
    state_5 = transition(state_4, 1)
    assert state_5.cards == ("Rio", "Hanako", "Kikyou", "Aru", "Kisaki", "Sena", "Rio_Copy")
    assert state_5.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 5: Sena")

    # --- Step 6: Rio EX -> 対象: Hanako (slot 0) ---
    state_6 = transition(state_5, 0, target="Hanako")
    assert state_6.cards == ("Rio_Copy", "Hanako", "Kikyou", "Aru", "Kisaki", "Sena", "Rio")
    assert state_6.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 6: Rio to Hanako, ゲージは200(Max)に")

    # --- Step 7: Rio_Copy EX (slot 0) ---
    state_7 = transition(state_6, 0)
    assert state_7.cards == ("Aru", "Hanako", "Kikyou", "Kisaki", "Sena", "Rio", "Rio_Copy")
    assert state_7.get_env("hanako_gauge", 0) == 200  # 代理実行なのでゲージは増減しない
    print("[OK] Step 7: Rio_copy, ゲージは200のまま")

    # --- Step 8: Hanako EX (slot 1) ---
    state_8 = transition(state_7, 1)
    assert state_8.cards == ("Aru", "Hanako", "Kikyou", "Kisaki", "Sena", "Rio", "Rio_Copy")
    assert state_8.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 8: Hanako, ゲージを100消費し手札に留まる")

    # --- Step 9: Hanako EX (slot 1) ---
    state_9 = transition(state_8, 1)
    assert state_9.cards == ("Aru", "Hanako", "Kikyou", "Kisaki", "Sena", "Rio", "Rio_Copy")
    assert state_9.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 9: Hanakoが再度EXを使用ゲージを100消費し手札に留まる")

    # --- Step 10: Hanako EX (slot 1) ---
    state_10 = transition(state_9, 1)
    assert state_10.cards == ("Aru", "Kisaki", "Kikyou", "Sena", "Rio", "Hanako", "Rio_Copy")
    assert state_10.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 10: Hanakoがゲージ0でEXを使用通常通りサイクルする")

    # =========================================================================
    # フェーズ2: アル セナ リオ キサキ ハナコ(コピー)
    # state_10: ハナコは手札におり、ゲージは0
    # =========================================================================

    # --- Step 11: Aru EX ---
    state_11 = transition(state_10, 0)
    assert state_11.cards == ("Sena", "Kisaki", "Kikyou", "Rio", "Hanako", "Aru", "Rio_Copy")
    assert state_11.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 11: Aru、水ゲージ40")

    # --- Step 12: Sena EX ---
    state_12 = transition(state_11, 0)
    assert state_12.cards == ("Rio", "Kisaki", "Kikyou", "Hanako", "Aru", "Sena", "Rio_Copy")
    assert state_12.get_env("hanako_gauge", 0) == 80

    print("[OK] Step 12: Sena、水ゲージ80")

    # --- Step 13: Rio EX -> Target: Hanako ---
    state_13 = transition(state_12, 0, target="Hanako")
    assert state_13.cards == ("Rio_Copy", "Kisaki", "Kikyou", "Hanako", "Aru", "Sena", "Rio")
    assert state_13.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 13: Rioコピー, 水ゲージ120")

    # --- Step 14: Kisaki EX ---
    state_14 = transition(state_13, 1)
    assert state_14.cards == ("Rio_Copy", "Hanako", "Kikyou", "Aru", "Sena", "Kisaki", "Rio")
    assert state_14.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 14: Kisaki, 水ゲージ160")

    # --- Step 15: Rio_Copy EX (Hanakoの代理実行) ---
    # 【判定】ハナコは既に手札にいるため、即ドローは発動せず通常サイクル
    state_15 = transition(state_14, 0)
    assert state_15.cards == ("Aru", "Hanako", "Kikyou", "Sena", "Kisaki", "Rio", "Rio_Copy")
    assert state_15.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 15: Rio_Copy, Hanakoは手札にいるためドロー不発(ゲージ160維持)")

    # =========================================================================
    # フェーズ3: 即 キキョウ ハナコ ハナコ アル ハナコ リオ→ハナコ ハナコ(コピー)
    # =========================================================================

    # --- Step 16: Kikyou EX (slot 2) ---
    state_16 = transition(state_15, 2)
    assert state_16.cards == ("Aru", "Hanako", "Sena", "Kisaki", "Rio", "Kikyou", "Rio_Copy")
    assert state_16.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 16: Kikyou、水ゲージ200 (MAX)")

    # --- Step 17: Hanako EX (slot 1) ---
    state_17 = transition(state_16, 1)
    assert state_17.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 17: Hanako(1連目), ゲージ100消費し手札維持")

    # --- Step 18: Hanako EX (slot 1) ---
    state_18 = transition(state_17, 1)
    assert state_18.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 18: Hanako(2連目), ゲージ100消費し手札維持")

    # --- Step 19: Aru EX (slot 0) ---
    state_19 = transition(state_18, 0)
    assert state_19.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 19: Aru, 水ゲージ40")

    # --- Step 20: Hanako EX (slot 1) ---
    # ゲージ不足(40)のため、ここでハナコは手札を離れサイクルする
    state_20 = transition(state_19, 1)
    assert state_20.cards == ("Kisaki", "Rio", "Sena", "Kikyou", "Aru", "Hanako", "Rio_Copy")
    assert state_20.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 20: Hanako(3連目), ゲージ不足で通常サイクル")

    # --- Step 21: Rio EX -> Target: Hanako (slot 1) ---
    state_21 = transition(state_20, 1, target="Hanako")
    assert state_21.cards == ("Kisaki", "Rio_Copy", "Sena", "Kikyou", "Aru", "Hanako", "Rio")
    assert state_21.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 21: Rioコピー")

    # --- Step 22: Rio_Copy EX (slot 1) ---
    state_22 = transition(state_21, 1)
    assert state_22.cards == ("Kisaki", "Kikyou", "Sena", "Aru", "Hanako", "Rio", "Rio_Copy")
    assert state_22.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 22: Rio_Copy")
    print(">>> [CHECK] フェーズ3終了時の手札整合性 OK")

    # =========================================================================
    # フェーズ4: セナ キサキ ハナコ ハナコ リオ→ハナコ ハナコ(コピー), ハナコ
    # =========================================================================

    # --- Step 23: Sena EX (slot 2) ---
    state_23 = transition(state_22, 2)
    assert state_23.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 23: Sena")

    # --- Step 24: Kisaki EX (slot 0) ---
    state_24 = transition(state_23, 0)
    assert state_24.cards == ("Hanako", "Kikyou", "Aru", "Rio", "Sena", "Kisaki", "Rio_Copy")
    assert state_24.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 24: Kisaki")

    # --- Step 25: Hanako EX (slot 0) ---
    state_25 = transition(state_24, 0)
    assert state_25.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 25: Hanako(1連目), 手札維持")

    # --- Step 26: Hanako EX (slot 0) ---
    # ゲージ不足によりサイクルし、次にRioが手札に入る
    state_26 = transition(state_25, 0)
    assert state_26.cards == ("Rio", "Kikyou", "Aru", "Sena", "Kisaki", "Hanako", "Rio_Copy")
    assert state_26.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 26: Hanako(2連目), 通常サイクル")

    # --- Step 27: Rio EX -> Target: Hanako (slot 0) ---
    state_27 = transition(state_26, 0, target="Hanako")
    assert state_27.cards == ("Rio_Copy", "Kikyou", "Aru", "Sena", "Kisaki", "Hanako", "Rio")
    assert state_27.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 27: Rioコピー")

    # --- Step 28: Rio_Copy EX (slot 0) ---
    state_28 = transition(state_27, 0)
    assert state_28.cards == ("Hanako", "Kikyou", "Aru", "Sena", "Kisaki", "Rio", "Rio_Copy")
    assert state_28.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 28: Rio_Copy")
    print(">>> [CHECK] フェーズ4 OK")

    # =========================================================================
    # フェーズ5: ハナコ セナ キサキ リオ→ハナコ アル ハナコ キキョウ セナ キサキ リオ(コピー) ハナコ ハナコ
    # （Step 28で即ドローしたため、ここで即座にハナコが撃てる！）
    # =========================================================================

    state_29 = transition(state_28, 0)  # Hanako (ゲージ0のため控えへサイクル)
    assert state_29.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 29: Hanako, 即ドローされたハナコを消化(サイクル)")

    state_30 = transition(state_29, 0)  # Sena (0 -> 40)
    assert state_30.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 30: Sena")

    state_31 = transition(state_30, 0)  # Kisaki (40 -> 80)
    assert state_31.cards == ("Rio", "Kikyou", "Aru", "Hanako", "Sena", "Kisaki", "Rio_Copy")
    assert state_31.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 31: Kisaki")

    state_32 = transition(state_31, 0, target="Hanako")  # Rio (80 -> 120)
    assert state_32.cards == ("Rio_Copy", "Kikyou", "Aru", "Hanako", "Sena", "Kisaki", "Rio")
    assert state_32.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 32: Rio")

    state_33 = transition(state_32, 2)  # Aru (120 -> 160)
    assert state_33.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 33: Aru")

    state_34 = transition(state_33, 2)  # Hanako (160 -> 60 / 手札維持)
    assert state_34.cards == ("Rio_Copy", "Kikyou", "Hanako", "Sena", "Kisaki", "Aru", "Rio")
    assert state_34.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 34: Hanako")

    state_35 = transition(state_34, 1)  # Kikyou (60 -> 100)
    print("[OK] Step 35: Kikyou")

    state_36 = transition(state_35, 1)  # Sena (100 -> 140)
    print("[OK] Step 36: Sena")

    state_37 = transition(state_36, 1)  # Kisaki (140 -> 180)
    print(state_37.cards)
    assert state_37.cards == ("Rio_Copy", "Aru", "Hanako", "Kikyou", "Sena", "Kisaki", "Rio")
    assert state_37.get_env("hanako_gauge", 0) == 180
    print("[OK] Step 37: Kisaki")

    # 【判定】ハナコは手札にいるため、即ドロー不発
    state_38 = transition(state_37, 0)  # Rio_Copy
    assert state_38.get_env("hanako_gauge", 0) == 180
    print("[OK] Step 38: Rio_Copy使用ハナコは手札にいるためドロー不発(ゲージ180維持)")

    state_39 = transition(state_38, 2)  # Hanako (180 -> 80 / 手札維持)
    assert state_39.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 39: Hanako")

    state_40 = transition(state_39, 2)  # Hanako (80のため控えへサイクル)
    assert state_40.cards == ("Kikyou", "Aru", "Sena", "Kisaki", "Rio", "Hanako", "Rio_Copy")
    assert state_40.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 40: Hanako")

    # =========================================================================
    # フェーズ6: キキョウ アル リオ→ハナコ キサキ ハナコ(コピー) ハナコ ハナコ ハナコ
    # =========================================================================

    state_41 = transition(state_40, 0)  # Kikyou (80 -> 120)
    print("[OK] Step 41: Kikyou")

    state_42 = transition(state_41, 1)  # Aru (120 -> 160)
    assert state_42.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 42: Aru")

    state_43 = transition(state_42, 1, target="Hanako")  # Rio (160 -> 200)
    assert state_43.cards == ("Kisaki", "Rio_Copy", "Sena", "Hanako", "Kikyou", "Aru", "Rio")
    assert state_43.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 43: Rio")

    state_44 = transition(state_43, 0)  # Kisaki (200 MAX)
    assert state_44.cards == ("Hanako", "Rio_Copy", "Sena", "Kikyou", "Aru", "Kisaki", "Rio")
    assert state_44.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 44: Kisaki")

    # 【判定】ハナコは手札にいるため、即ドロー不発
    state_45 = transition(state_44, 1)  # Rio_Copy
    assert state_45.cards == ("Hanako", "Kikyou", "Sena", "Aru", "Kisaki", "Rio", "Rio_Copy")
    assert state_45.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 45: Rio_Copy使用ドロー不発(ゲージ200維持)")

    state_46 = transition(state_45, 0)  # Hanako (200 -> 100)
    assert state_46.cards == ("Hanako", "Kikyou", "Sena", "Aru", "Kisaki", "Rio", "Rio_Copy")
    assert state_46.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 46: Hanako")

    state_47 = transition(state_46, 0)  # Hanako (100 -> 0)
    assert state_47.cards == ("Hanako", "Kikyou", "Sena", "Aru", "Kisaki", "Rio", "Rio_Copy")
    assert state_47.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 47: Hanako")

    state_48 = transition(state_47, 0)  # Hanako (0のためサイクル)
    assert state_48.cards == ("Aru", "Kikyou", "Sena", "Kisaki", "Rio", "Hanako", "Rio_Copy")
    assert state_48.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 48: Hanako")
    print(">>> [CHECK] フェーズ6 OK")


if __name__ == "__main__":
    test_rio_hanako_integration

    print("\n[OK] クロカゲ戦タイムライン完走 (手札外実行含む)")
