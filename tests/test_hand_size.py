from __future__ import annotations

from ba_exsim.core.state import State

# hand_size!=3 での実行(カード消失バグの再現など)は tests/data/scenarios/hand_size/ にある。


def test_state_hand_deck_properties():
    """State.hand/deckはhand_sizeに基づいてcardsを正しく分割する。"""
    state = State(cards=("A", "B", "C", "D", "E", "F"), hand_size=3)
    assert state.hand == ("A", "B", "C")
    assert state.deck == ("D", "E", "F")

    state6 = State(cards=("A", "B", "C", "D", "E", "F", "G", "H", "I", "J"), hand_size=6)
    assert state6.hand == ("A", "B", "C", "D", "E", "F")
    assert state6.deck == ("G", "H", "I", "J")

