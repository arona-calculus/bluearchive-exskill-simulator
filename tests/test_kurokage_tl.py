from __future__ import annotations
from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec


# ---------------------------------------------------------------------------
# 共通セットアップ
# ---------------------------------------------------------------------------

def build_simulator() -> Simulator:
    return Simulator([
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Kisaki"),
        GenericSpec("Kikyou"),
        GenericSpec("Sena"),
        RioCopySpec(),
    ])


# ---------------------------------------------------------------------------
# フェーズ1: ハナコ セナ キキョウ アル リオ キサキ
# ハナコがゲージ不足でサイクル → ゲージを積み上げ → リオがコピー →
# コピーが代理実行（ゲージ増減なし） → ハナコが2連続手札留まり → ゲージ切れサイクル
# ---------------------------------------------------------------------------

def test_phase1() -> None:
    """
    フェーズ1: ハナコ通常サイクル、リオのコピー、ハナコ2連続手札留まり
    終了時: hanako_gauge=0, Hanakoは山札末尾
    """
    print("\n=== フェーズ1 ===")
    sim = build_simulator()
    initial_cards = ("Hanako_Swimsuit", "Sena", "Kikyou", "Aru", "Rio", "Kisaki")
    state = sim.initialize_state(initial_cards)

    assert state.cards == ("Hanako_Swimsuit", "Sena", "Kikyou", "Aru", "Rio", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] 初期状態")

    state = sim.play(1)  # Sena
    assert state.cards == ("Hanako_Swimsuit", "Aru", "Kikyou", "Rio", "Kisaki", "Sena")
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 1: Sena, ゲージ40")

    state = sim.play(0)  # Hanako（ゲージ不足）
    assert state.cards == ("Rio", "Aru", "Kikyou", "Kisaki", "Sena", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 2: Hanako, ゲージ不足で通常サイクル")

    state = sim.play(1)  # Aru
    assert state.cards == ("Rio", "Kisaki", "Kikyou", "Sena", "Hanako_Swimsuit", "Aru")
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 3: Aru, ゲージ80")

    state = sim.play(1)  # Kisaki
    assert state.cards == ("Rio", "Sena", "Kikyou", "Hanako_Swimsuit", "Aru", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 4: Kisaki, ゲージ120")

    state = sim.play(1)  # Sena
    assert state.cards == ("Rio", "Hanako_Swimsuit", "Kikyou", "Aru", "Kisaki", "Sena")
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 5: Sena, ゲージ160")

    state = sim.play(0, target="Hanako_Swimsuit")  # Rio → Rio_Copy
    assert state.cards == ("Rio_Copy", "Hanako_Swimsuit", "Kikyou", "Aru", "Kisaki", "Sena")
    assert state.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 6: Rio → Rio_Copy, ゲージ200(MAX)")

    state = sim.play(0)  # Rio_Copy（代理実行、ゲージ増減なし）
    assert state.cards == ("Aru", "Hanako_Swimsuit", "Kikyou", "Kisaki", "Sena", "Rio")
    assert state.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 7: Rio_Copy, 代理実行、ゲージ200維持")

    state = sim.play(1)  # Hanako（ゲージ200 → 100、手札留まり）
    assert state.cards == ("Aru", "Hanako_Swimsuit", "Kikyou", "Kisaki", "Sena", "Rio")
    assert state.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 8: Hanako, ゲージ100消費、手札留まり")

    state = sim.play(1)  # Hanako（ゲージ100 → 0、手札留まり）
    assert state.cards == ("Aru", "Hanako_Swimsuit", "Kikyou", "Kisaki", "Sena", "Rio")
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 9: Hanako, ゲージ100消費、手札留まり")

    state = sim.play(1)  # Hanako（ゲージ切れ、通常サイクル）
    assert state.cards == ("Aru", "Kisaki", "Kikyou", "Sena", "Rio", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 10: Hanako, ゲージ切れで通常サイクル")

    print(">>> フェーズ1 OK")


# ---------------------------------------------------------------------------
# フェーズ2: アル キサキ キキョウ セナ リオ ハナコ
# リオがコピー → キサキがゲージ積み → コピーが代理実行（ハナコ手札にいるため即ドロー不発）
# ---------------------------------------------------------------------------

def test_phase2() -> None:
    """
    フェーズ2: リオのコピー後、ハナコ手札在中で即ドロー不発を確認
    開始時: cards=("Aru", "Kisaki", "Kikyou", "Sena", "Rio", "Hanako_Swimsuit"), hanako_gauge=0
    終了時: hanako_gauge=160, Hanakoは手札に在中
    """
    print("\n=== フェーズ2 ===")
    sim = build_simulator()
    sim.state = sim.initialize_state(
        ("Aru", "Kisaki", "Kikyou", "Sena", "Rio", "Hanako_Swimsuit"),
        env={"hanako_gauge": 0},
    )

    state = sim.play(0)  # Aru
    assert state.cards == ("Sena", "Kisaki", "Kikyou", "Rio", "Hanako_Swimsuit", "Aru")
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 11: Aru, ゲージ40")

    state = sim.play(0)  # Sena
    assert state.cards == ("Rio", "Kisaki", "Kikyou", "Hanako_Swimsuit", "Aru", "Sena")
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 12: Sena, ゲージ80")

    state = sim.play(0, target="Hanako_Swimsuit")  # Rio → Rio_Copy
    assert state.cards == ("Rio_Copy", "Kisaki", "Kikyou", "Hanako_Swimsuit", "Aru", "Sena")
    assert state.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 13: Rio → Rio_Copy, ゲージ120")

    state = sim.play(1)  # Kisaki
    assert state.cards == ("Rio_Copy", "Hanako_Swimsuit", "Kikyou", "Aru", "Sena", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 14: Kisaki, ゲージ160")

    state = sim.play(0)  # Rio_Copy（ハナコ手札在中のため即ドロー不発）
    assert state.cards == ("Aru", "Hanako_Swimsuit", "Kikyou", "Sena", "Kisaki", "Rio")
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 15: Rio_Copy, ハナコ手札在中のため即ドロー不発、ゲージ160維持")

    print(">>> フェーズ2 OK")


# ---------------------------------------------------------------------------
# フェーズ3: アル ハナコ キキョウ セナ キサキ リオ
# ハナコ2連続手札留まり → ゲージ切れサイクル → リオがコピー →
# コピーが代理実行（ハナコ手札在中のため即ドロー不発）
# ---------------------------------------------------------------------------

def test_phase3() -> None:
    """
    フェーズ3: ハナコ連続使用、ゲージ切れ後リオがコピー、即ドロー不発
    開始時: cards=("Aru", "Hanako_Swimsuit", "Kikyou", "Sena", "Kisaki", "Rio"), hanako_gauge=160
    終了時: hanako_gauge=80, Hanakoは山札内
    """
    print("\n=== フェーズ3 ===")
    sim = build_simulator()
    sim.state = sim.initialize_state(
        ("Aru", "Hanako_Swimsuit", "Kikyou", "Sena", "Kisaki", "Rio"),
        env={"hanako_gauge": 160},
    )

    state = sim.play(2)  # Kikyou
    assert state.cards == ("Aru", "Hanako_Swimsuit", "Sena", "Kisaki", "Rio", "Kikyou")
    assert state.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 16: Kikyou, ゲージ200(MAX)")

    state = sim.play(1)  # Hanako（ゲージ200 → 100、手札留まり）
    assert state.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 17: Hanako(1連目), ゲージ100消費、手札留まり")

    state = sim.play(1)  # Hanako（ゲージ100 → 0、手札留まり）
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 18: Hanako(2連目), ゲージ100消費、手札留まり")

    state = sim.play(0)  # Aru
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 19: Aru, ゲージ40")

    state = sim.play(1)  # Hanako（ゲージ不足、通常サイクル）
    assert state.cards == ("Kisaki", "Rio", "Sena", "Kikyou", "Aru", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 20: Hanako(3連目), ゲージ不足で通常サイクル")

    state = sim.play(1, target="Hanako_Swimsuit")  # Rio → Rio_Copy
    assert state.cards == ("Kisaki", "Rio_Copy", "Sena", "Kikyou", "Aru", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 21: Rio → Rio_Copy, ゲージ80")

    state = sim.play(1)  # Rio_Copy（ハナコ手札在中のため即ドロー不発）
    assert state.cards == ("Kisaki", "Kikyou", "Sena", "Aru", "Hanako_Swimsuit", "Rio")
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 22: Rio_Copy, ハナコ手札在中のため即ドロー不発、ゲージ80維持")

    print(">>> フェーズ3 OK")


# ---------------------------------------------------------------------------
# フェーズ4: キサキ キキョウ セナ アル ハナコ リオ
# ハナコが手札留まりからゲージ切れサイクル → リオがコピー →
# コピーが代理実行（ハナコ手札外のため即ドロー発動）
# ---------------------------------------------------------------------------

def test_phase4() -> None:
    """
    フェーズ4: ハナコ連続使用後サイクル、リオのコピー後即ドロー発動
    開始時: cards=("Kisaki", "Kikyou", "Sena", "Aru", "Hanako_Swimsuit", "Rio"), hanako_gauge=80
    終了時: hanako_gauge=0, Hanakoが即ドローでスロット0に在中
    """
    print("\n=== フェーズ4 ===")
    sim = build_simulator()
    sim.state = sim.initialize_state(
        ("Kisaki", "Kikyou", "Sena", "Aru", "Hanako_Swimsuit", "Rio"),
        env={"hanako_gauge": 80},
    )

    state = sim.play(2)  # Sena
    assert state.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 23: Sena, ゲージ120")

    state = sim.play(0)  # Kisaki
    assert state.cards == ("Hanako_Swimsuit", "Kikyou", "Aru", "Rio", "Sena", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 24: Kisaki, ゲージ160")

    state = sim.play(0)  # Hanako（ゲージ160 → 60、手札留まり）
    assert state.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 25: Hanako(1連目), ゲージ100消費、手札留まり")

    state = sim.play(0)  # Hanako（ゲージ不足、通常サイクル）
    assert state.cards == ("Rio", "Kikyou", "Aru", "Sena", "Kisaki", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 26: Hanako(2連目), ゲージ不足で通常サイクル")

    state = sim.play(0, target="Hanako_Swimsuit")  # Rio → Rio_Copy
    assert state.cards == ("Rio_Copy", "Kikyou", "Aru", "Sena", "Kisaki", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 27: Rio → Rio_Copy, ゲージ100")

    state = sim.play(0)  # Rio_Copy（ハナコ手札外かつゲージ≥100のため即ドロー発動）
    assert state.cards == ("Hanako_Swimsuit", "Kikyou", "Aru", "Sena", "Kisaki", "Rio")
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 28: Rio_Copy, ハナコ即ドロー発動、ゲージ100消費（0）")

    print(">>> フェーズ4 OK")


# ---------------------------------------------------------------------------
# フェーズ5: ハナコ セナ キサキ リオ→ハナコ アル ハナコ…
# 即ドローされたハナコを消化 → ゲージを積み上げ → リオがコピー →
# ハナコ手札留まりからゲージ切れ
# ---------------------------------------------------------------------------

def test_phase5() -> None:
    """
    フェーズ5: 即ドロー後のハナコ消化、リオのコピー、ハナコ手札留まり連続
    開始時: cards=("Hanako_Swimsuit", "Kikyou", "Aru", "Sena", "Kisaki", "Rio"), hanako_gauge=0
    終了時: hanako_gauge=80, Hanakoは手札に在中
    """
    print("\n=== フェーズ5 ===")
    sim = build_simulator()
    sim.state = sim.initialize_state(
        ("Hanako_Swimsuit", "Kikyou", "Aru", "Sena", "Kisaki", "Rio"),
        env={"hanako_gauge": 0},
    )

    state = sim.play(0)  # Hanako（ゲージ0のため通常サイクル）
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 29: Hanako, 即ドロー後ゲージ切れでサイクル")

    state = sim.play(0)  # Sena
    assert state.get_env("hanako_gauge", 0) == 40
    print("[OK] Step 30: Sena, ゲージ40")

    state = sim.play(0)  # Kisaki
    assert state.cards == ("Rio", "Kikyou", "Aru", "Hanako_Swimsuit", "Sena", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 31: Kisaki, ゲージ80")

    state = sim.play(0, target="Hanako_Swimsuit")  # Rio → Rio_Copy
    assert state.cards == ("Rio_Copy", "Kikyou", "Aru", "Hanako_Swimsuit", "Sena", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 120
    print("[OK] Step 32: Rio → Rio_Copy, ゲージ120")

    state = sim.play(2)  # Aru
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 33: Aru, ゲージ160")

    state = sim.play(2)  # Hanako（ゲージ160 → 60、手札留まり）
    assert state.cards == ("Rio_Copy", "Kikyou", "Hanako_Swimsuit", "Sena", "Kisaki", "Aru")
    assert state.get_env("hanako_gauge", 0) == 60
    print("[OK] Step 34: Hanako, ゲージ100消費、手札留まり")

    state = sim.play(1)  # Kikyou
    print("[OK] Step 35: Kikyou, ゲージ100")

    state = sim.play(1)  # Sena
    print("[OK] Step 36: Sena, ゲージ140")

    state = sim.play(1)  # Kisaki
    assert state.cards == ("Rio_Copy", "Aru", "Hanako_Swimsuit", "Kikyou", "Sena", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 180
    print("[OK] Step 37: Kisaki, ゲージ180")

    state = sim.play(0)  # Rio_Copy（ハナコ手札在中のため即ドロー不発）
    assert state.get_env("hanako_gauge", 0) == 180
    print("[OK] Step 38: Rio_Copy, ハナコ手札在中のため即ドロー不発、ゲージ180維持")

    state = sim.play(2)  # Hanako（ゲージ180 → 80、手札留まり）
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 39: Hanako, ゲージ100消費、手札留まり")

    state = sim.play(2)  # Hanako（ゲージ不足、通常サイクル）
    assert state.cards == ("Kikyou", "Aru", "Sena", "Kisaki", "Rio", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 80
    print("[OK] Step 40: Hanako, ゲージ不足で通常サイクル")

    print(">>> フェーズ5 OK")


# ---------------------------------------------------------------------------
# フェーズ6: キキョウ アル リオ→ハナコ キサキ…
# リオがコピー → キサキがゲージ積み → コピーが代理実行（ハナコ手札在中のため即ドロー不発）
# → ハナコ3連続手札留まりからゲージ切れサイクル
# ---------------------------------------------------------------------------

def test_phase6() -> None:
    """
    フェーズ6: リオのコピー後即ドロー不発、ハナコ3連続使用
    開始時: cards=("Kikyou", "Aru", "Sena", "Kisaki", "Rio", "Hanako_Swimsuit"), hanako_gauge=80
    終了時: hanako_gauge=0, Hanakoは山札末尾
    """
    print("\n=== フェーズ6 ===")
    sim = build_simulator()
    sim.state = sim.initialize_state(
        ("Kikyou", "Aru", "Sena", "Kisaki", "Rio", "Hanako_Swimsuit"),
        env={"hanako_gauge": 80},
    )

    state = sim.play(0)  # Kikyou
    print("[OK] Step 41: Kikyou, ゲージ120")

    state = sim.play(1)  # Aru
    assert state.get_env("hanako_gauge", 0) == 160
    print("[OK] Step 42: Aru, ゲージ160")

    state = sim.play(1, target="Hanako_Swimsuit")  # Rio → Rio_Copy
    assert state.cards == ("Kisaki", "Rio_Copy", "Sena", "Hanako_Swimsuit", "Kikyou", "Aru")
    assert state.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 43: Rio → Rio_Copy, ゲージ200(MAX)")

    state = sim.play(0)  # Kisaki
    assert state.cards == ("Hanako_Swimsuit", "Rio_Copy", "Sena", "Kikyou", "Aru", "Kisaki")
    assert state.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 44: Kisaki, ゲージ200維持(MAX)")

    state = sim.play(1)  # Rio_Copy（ハナコ手札在中のため即ドロー不発）
    assert state.cards == ("Hanako_Swimsuit", "Kikyou", "Sena", "Aru", "Kisaki", "Rio")
    assert state.get_env("hanako_gauge", 0) == 200
    print("[OK] Step 45: Rio_Copy, ハナコ手札在中のため即ドロー不発、ゲージ200維持")

    state = sim.play(0)  # Hanako（ゲージ200 → 100、手札留まり）
    assert state.cards == ("Hanako_Swimsuit", "Kikyou", "Sena", "Aru", "Kisaki", "Rio")
    assert state.get_env("hanako_gauge", 0) == 100
    print("[OK] Step 46: Hanako(1連目), ゲージ100消費、手札留まり")

    state = sim.play(0)  # Hanako（ゲージ100 → 0、手札留まり）
    assert state.cards == ("Hanako_Swimsuit", "Kikyou", "Sena", "Aru", "Kisaki", "Rio")
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 47: Hanako(2連目), ゲージ100消費、手札留まり")

    state = sim.play(0)  # Hanako（ゲージ切れ、通常サイクル）
    assert state.cards == ("Aru", "Kikyou", "Sena", "Kisaki", "Rio", "Hanako_Swimsuit")
    assert state.get_env("hanako_gauge", 0) == 0
    print("[OK] Step 48: Hanako(3連目), ゲージ切れで通常サイクル")

    print(">>> フェーズ6 OK")


# ---------------------------------------------------------------------------
# 全フェーズ通し実行
# ---------------------------------------------------------------------------

def test_rio_hanako_integration_kurokage():
    """クロカゲ戦タイムライン全フェーズ通し"""
    test_phase1()
    test_phase2()
    test_phase3()
    test_phase4()
    test_phase5()
    test_phase6()
    print("\n[OK] クロカゲ戦タイムライン完走 (手札外実行含む)")


if __name__ == "__main__":
    test_rio_hanako_integration_kurokage()
