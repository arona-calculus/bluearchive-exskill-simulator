from __future__ import annotations

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.state import State
from ba_exsim.specs.generic import GenericSpec


def test_state_hand_deck_properties():
    """State.hand/deckはhand_sizeに基づいてcardsを正しく分割する。"""
    state = State(cards=("A", "B", "C", "D", "E", "F"), hand_size=3)
    assert state.hand == ("A", "B", "C")
    assert state.deck == ("D", "E", "F")

    state6 = State(cards=("A", "B", "C", "D", "E", "F", "G", "H", "I", "J"), hand_size=6)
    assert state6.hand == ("A", "B", "C", "D", "E", "F")
    assert state6.deck == ("G", "H", "I", "J")


def test_draw_card_with_non_default_hand_size():
    """
    hand_size=6の盤面で手札中央(index 3)のカードを使用しても、
    どのカードも消失せずに正しく山札の先頭(index=hand_size)が引かれること。

    共有リンクで報告された実際のバグ(hand_size=6でHifumiをプレイしたら
    Hinaが手札からも山札からも消失した)の再現テスト。
    """
    specs = [GenericSpec(n) for n in
             ("Aru_Dress", "Eimi", "Haruna", "Hifumi", "Hina", "Hoshino", "Iori", "Maki", "Neru", "Izumi")]
    initial_cards = (
        "Aru_Dress", "Eimi", "Haruna", "Hifumi", "Hina", "Hoshino",  # 手札(6枚)
        "Iori", "Maki", "Neru", "Izumi",  # 山札
    )

    sim = Simulator(specs)
    sim.initialize_state(initial_cards, hand_size=6)

    state = sim.play(3)  # Hifumi(手札index 3)を使用

    # 全10枚が過不足なく残っていること(消失したり重複したりしない)
    assert sorted(c for c in state.cards if c is not None) == sorted(initial_cards)
    assert None not in state.cards

    # 山札の先頭(本来のindex=hand_size=6、つまりIori)が正しく引かれていること
    assert state.hand == ("Aru_Dress", "Eimi", "Haruna", "Iori", "Hina", "Hoshino")
    assert state.deck == ("Maki", "Neru", "Izumi", "Hifumi")


def test_draw_card_with_hand_size_four():
    """hand_size=4でも同様にカードが消失しないこと。"""
    specs = [GenericSpec(n) for n in
             ("Aru_Dress", "Eimi", "Haruna", "Hifumi", "Hina", "Hoshino")]
    initial_cards = ("Aru_Dress", "Eimi", "Haruna", "Hifumi", "Hina", "Hoshino")

    sim = Simulator(specs)
    sim.initialize_state(initial_cards, hand_size=4)

    state = sim.play(3)  # Hifumi(手札index 3)を使用

    assert sorted(c for c in state.cards if c is not None) == sorted(initial_cards)
    assert None not in state.cards
    assert state.hand == ("Aru_Dress", "Eimi", "Haruna", "Hina")
    assert state.deck == ("Hoshino", "Hifumi")


def test_play_by_name_with_non_default_hand_size():
    """
    Simulator.play_by_nameはhand_size=3決め打ちではなく、実際の手札サイズを見て
    index 3以降の手札にいるキャラも正しく見つけられること。
    """
    specs = [GenericSpec(n) for n in ("Aru", "Eri", "Kisaki", "Mine", "Miyako", "Seia")]
    initial_cards = ("Aru", "Eri", "Kisaki", "Mine", "Miyako", "Seia")

    sim = Simulator(specs)
    sim.initialize_state(initial_cards, hand_size=6)

    # "Mine"は手札index 3(hand_size=3決め打ちなら「手札にない」と誤判定されていた)
    state = sim.play_by_name("Mine")
    assert sorted(c for c in state.cards if c is not None) == sorted(initial_cards)
