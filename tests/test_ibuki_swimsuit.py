from __future__ import annotations

import pytest

from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.ibuki_swimsuit import IbukiSwimsuitSpec

HAND_SIZE = 3


def _play_from_hand(sim: Simulator, name: str, target: str = ""):
    """テスト用ヘルパー: 実際のAPIと同様、手札(先頭HAND_SIZE枚)の中からのみ選んで使用する。"""
    hand = sim.state.cards[:HAND_SIZE]
    assert name in hand, f"{name} は手札 {hand} にありません"
    return sim.play(hand.index(name), target)


def _play_any_non_friend_from_hand(sim: Simulator, friends: tuple[str, ...]):
    """手札の中から「お友達」でも本人でもないカードを1枚選んで使用する(場をつなぐため)。"""
    hand = sim.state.cards[:HAND_SIZE]
    for name in hand:
        if name != "Ibuki_Swimsuit" and name not in friends:
            return _play_from_hand(sim, name)
    raise AssertionError(f"つなぎ役のカードが手札 {hand} に見つかりません")


def test_ibuki_swimsuit_full_behavior():
    """
    イブキ(水着)の代数的な基本挙動を検証する:
    1. EX1使用時、お友達2人を指定し、自身が次のドローで即座に手札へ戻る
       (=手札の並びが変化しない)。
    2. お友達がカードを使う度に貝殻を3個獲得する。
    3. 貝殻が12個に達すると「貝殻のお花」を獲得し、以降貝殻が増えない。
    4. お友達以外のカード使用では貝殻が増えない。
    5. EX2(指定済み)使用時は状態が変化せず、通常通りサイクルする。
    """
    specs = [
        IbukiSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Eri"),
        GenericSpec("Kisaki"),
        GenericSpec("Mine"),
        GenericSpec("Miyako"),
    ]
    initial_cards = ("Ibuki_Swimsuit", "Aru", "Eri", "Kisaki", "Mine", "Miyako")

    sim = Simulator(specs)
    sim.initialize_state(initial_cards)

    # --- Step 1: EX1でアル・エリを「お友達」に指定 ---
    # 期待値: 即座に手札へ戻る(pending_force_draw)ため、手札の並びは変化しない
    state = _play_from_hand(sim, "Ibuki_Swimsuit", "Aru,Eri")
    assert state.cards == initial_cards
    assert state.env["ibuki_friends"] == ("Aru", "Eri")
    assert state.env["ibuki_shells"] == 0
    assert state.env["ibuki_shell_flower"] is False
    print("[OK] Step 1: お友達を指定し、イブキ自身が即座に手札へ戻りました。")

    # --- Step 2以降: お友達が手札に来るたびに使用し、貝殻が12(お花)に達するまで繰り返す。
    # お友達がいない間に引いた「お友達以外」のカードでは貝殻が増えないことも併せて検証する。
    expected_shells_sequence = []
    non_friend_played = False
    guard = 0
    while not state.env.get("ibuki_shell_flower", False):
        guard += 1
        assert guard < 30, "貝殻がお花にならないままループが終わりませんでした"
        hand = state.cards[:HAND_SIZE]
        friend_in_hand = next((n for n in hand if n in state.env["ibuki_friends"]), None)
        if friend_in_hand:
            state = _play_from_hand(sim, friend_in_hand)
            expected_shells_sequence.append(state.env["ibuki_shells"])
        else:
            shells_before = state.env.get("ibuki_shells", 0)
            state = _play_any_non_friend_from_hand(sim, state.env["ibuki_friends"])
            assert state.env.get("ibuki_shells", 0) == shells_before
            non_friend_played = True
    assert non_friend_played, "お友達以外のカードを使う場面が発生しませんでした"
    print("[OK] Step 2: お友達以外の使用では貝殻が増加しませんでした。")

    assert state.env["ibuki_shells"] == 0
    assert state.env["ibuki_shell_flower"] is True
    # 貝殻は 3, 6, 9 と増えたのち 12 到達で 0 にリセットされているはず
    assert expected_shells_sequence[-4:] == [3, 6, 9, 0]
    print(f"[OK] Step 3: 貝殻が {expected_shells_sequence} と増加し、お花を獲得しました。")

    # --- Step 4: お花獲得後、お友達が使用しても貝殻は増加しない ---
    guard = 0
    while True:
        guard += 1
        assert guard < 10
        hand = state.cards[:HAND_SIZE]
        friend_in_hand = next((n for n in hand if n in state.env["ibuki_friends"]), None)
        if friend_in_hand:
            state = _play_from_hand(sim, friend_in_hand)
            break
        state = _play_any_non_friend_from_hand(sim, state.env["ibuki_friends"])
    assert state.env["ibuki_shells"] == 0
    assert state.env["ibuki_shell_flower"] is True
    print("[OK] Step 4: 「貝殻のお花」獲得後は貝殻が増加しませんでした。")

    # --- Step 5: EX2(指定済み)を使用 → 状態を変えずに通常通りサイクルする ---
    guard = 0
    while "Ibuki_Swimsuit" not in state.cards[:HAND_SIZE]:
        guard += 1
        assert guard < 10
        state = _play_any_non_friend_from_hand(sim, state.env["ibuki_friends"])
    friends_before = state.env["ibuki_friends"]
    state = _play_from_hand(sim, "Ibuki_Swimsuit")
    assert state.env["ibuki_friends"] == friends_before
    assert "Ibuki_Swimsuit" not in state.cards[:HAND_SIZE]  # 通常のサイクルで手札から抜ける
    print("[OK] Step 5: EX2使用時は状態を変えずに通常通りサイクルしました。")


def test_ibuki_swimsuit_role_validation():
    """
    お友達指定はストライカーのみ許可される:
    1. SPECIALと判明しているキャラを含めるとValueErrorになる。
    2. STRIKER同士なら正常に指定できる。
    3. role情報が無いキャラ(未登録/カスタム)は許可される(除外しない)。
    """
    character_roles = {"Aru": "STRIKER", "Kisaki": "STRIKER", "Eri": "SPECIAL"}

    specs = [
        IbukiSwimsuitSpec(character_roles=character_roles),
        GenericSpec("Aru"),
        GenericSpec("Eri"),
        GenericSpec("Kisaki"),
        GenericSpec("Unknown_Custom"),
    ]

    # --- SPECIALを含む指定はエラーになる ---
    sim = Simulator(specs)
    sim.initialize_state(("Ibuki_Swimsuit", "Aru", "Eri", "Kisaki", "Unknown_Custom"))
    with pytest.raises(ValueError):
        sim.play_by_name("Ibuki_Swimsuit", target="Aru,Eri")
    print("[OK] SPECIALを含む指定でValueErrorが発生しました。")

    # --- STRIKER同士なら正常に指定できる ---
    sim2 = Simulator(specs)
    sim2.initialize_state(("Ibuki_Swimsuit", "Aru", "Eri", "Kisaki", "Unknown_Custom"))
    state = sim2.play_by_name("Ibuki_Swimsuit", target="Aru,Kisaki")
    assert state.env["ibuki_friends"] == ("Aru", "Kisaki")
    print("[OK] ストライカー同士の指定は成功しました。")

    # --- role不明のキャラは除外されず指定できる ---
    sim3 = Simulator(specs)
    sim3.initialize_state(("Ibuki_Swimsuit", "Aru", "Eri", "Kisaki", "Unknown_Custom"))
    state = sim3.play_by_name("Ibuki_Swimsuit", target="Aru,Unknown_Custom")
    assert state.env["ibuki_friends"] == ("Aru", "Unknown_Custom")
    print("[OK] role不明のキャラも指定できました。")


if __name__ == "__main__":
    test_ibuki_swimsuit_full_behavior()
    test_ibuki_swimsuit_role_validation()
