from __future__ import annotations
import itertools
from ba_exsim.core.simulator import Simulator
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.rio import RioSpec, RioCopySpec


def build_simulator() -> Simulator:
    return Simulator([
        RioSpec(),
        HanakoSwimsuitSpec(),
        GenericSpec("Aru"),
        GenericSpec("Seia"),
        GenericSpec("Hikari"),
        GenericSpec("Michiru"),
        RioCopySpec(),
    ])

def test_d33_kurogkage(initial_cards: tuple[str, ...]) -> tuple[str, ...]:
    """
    ハナコ/ヒカリ/アル/セイア/ミチル/リオ

    即ヒカリ
    即リオ
    8ハナコC
    即ドアル
    即セイア
    即ハナコ
    即ミチル
    即ハナコ
    03:28.966 リオ

    NS後ハナコ
    即ハナコC
    即ヒカリ
    即ミチル
    即ハナコ
    即ハナコ〆
    """
    sim = build_simulator()
    state = sim.initialize_state(initial_cards)

    init_state = state
    state = sim.play_by_name("Hikari")  # ヒカリ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ → ハナコ

    state = sim.play_by_name("Rio_Copy")  # Cハナコ
    # state = sim.play_by_name("Seia")  # セイア
    # state = sim.play_by_name("Aru")  # アル

    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        # print("ヒカリ裏セイア")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    elif init_state.cards[3] == "Michiru": # リオ裏ミチル
        # print("リオ裏ミチル")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア

    else:
        # print("ヒカリ裏ハナコ")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    

    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Michiru")  # ミチル → ハナコ
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ -> ハナコ

    # フェーズ移行
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    # print(state.cards)
    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        state = sim.play_by_name("Rio_Copy")  # Cハナコ
        state = sim.play_by_name("Hikari")  # ヒカリ
    else:
        state = sim.play_by_name("Hikari")  # ヒカリ
        state = sim.play_by_name("Rio_Copy")  # Cハナコ


    state = sim.play_by_name("Michiru")  # ミチル

    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    return state.cards


def test(members) -> None:

    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_d33_kurogkage(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")


def test_case1_tl(initial_cards: tuple[str, ...]) -> tuple[str, ...]:
    """
    ハナコ/ヒカリ/アル/セイア/ミチル/リオ

    即ヒカリ
    即リオ
    8ハナコC
    即ドアル
    即セイア
    即ハナコ
    即ミチル
    即ハナコ
    03:28.966 リオ

    NS後ハナコ
    即ハナコC
    即ヒカリ
    即ミチル
    即ハナコ
    即ハナコ〆
    """
    sim = build_simulator()
    state = sim.initialize_state(initial_cards)
    init_state = state
    state = sim.play_by_name("Hikari")  # ヒカリ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ → ハナコ
    state = sim.play_by_name("Rio_Copy")  # Cハナコ
    
    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        # print("ヒカリ裏セイア")
        state = sim.play_by_name("Seia")  # セイア
        state = sim.play_by_name("Aru")  # アル
    elif init_state.cards[3] == "Hanako_Swimsuit": # ヒカリ裏ハナコ
        # print("ヒカリ裏ハナコ")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    else: # ヒカリ裏ミチル
        # print("ヒカリ裏ミチル")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア

    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Michiru")  # ミチル → ハナコ
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ -> ハナコ

    # フェーズ移行
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    print(state.cards)
    if state.cards[0] == "Hikari":
        state = sim.play_by_name("Rio_Copy")  # Cハナコ
        state = sim.play_by_name("Hikari")  # ヒカリ
    else:
        state = sim.play_by_name("Hikari")  # ヒカリ
        state = sim.play_by_name("Rio_Copy")  # Cハナコ

    state = sim.play_by_name("Michiru")  # ミチル

    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    return state.cards


def test_case1(members) -> None:

    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_case1_tl(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")


def test_case2_tl(initial_cards: tuple[str, ...]) -> tuple[str, ...]:
    """
    ハナコ/ヒカリ/アル/セイア/ミチル/リオ

    即ヒカリ
    即リオ
    8ハナコC
    即ドアル
    即セイア
    即ハナコ
    即ミチル
    即ハナコ
    03:28.966 リオ

    NS後ハナコ
    即ハナコC
    即ヒカリ
    即ミチル
    即ハナコ
    即ハナコ〆
    """
    sim = build_simulator()
    state = sim.initialize_state(initial_cards)

    init_state = state
    state = sim.play_by_name("Hikari")  # ヒカリ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ → ハナコ

    state = sim.play_by_name("Rio_Copy")  # Cハナコ
    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        # print("ヒカリ裏セイア")
        state = sim.play_by_name("Seia")  # セイア
        state = sim.play_by_name("Aru")  # アル
    elif init_state.cards[3] == "Michiru": # リオ裏ミチル
        # print("リオ裏ミチル")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    else:
        # print("ヒカリ裏ハナコ")
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Michiru")  # ミチル → ハナコ
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ -> ハナコ

    # フェーズ移行
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    print(state.cards)
    if state.cards[0] == "Hikari":
        state = sim.play_by_name("Rio_Copy")  # Cハナコ
        state = sim.play_by_name("Hikari")  # ヒカリ
    else:
        state = sim.play_by_name("Hikari")  # ヒカリ
        state = sim.play_by_name("Rio_Copy")  # Cハナコ


    state = sim.play_by_name("Michiru")  # ミチル

    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    return state.cards


def test_case2(members) -> None:

    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_case2_tl(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")


def test_case3_tl(initial_cards: tuple[str, ...]) -> tuple[str, ...]:
    sim = build_simulator()
    state = sim.initialize_state(initial_cards)

    init_state = state
    state = sim.play_by_name("Hikari")  # ヒカリ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ → ハナコ

    state = sim.play_by_name("Rio_Copy")  # Cハナコ
    # state = sim.play_by_name("Seia")  # セイア
    # state = sim.play_by_name("Aru")  # アル

    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        state = sim.play_by_name("Seia")  # セイア
        state = sim.play_by_name("Aru")  # アル
    elif init_state.cards[3] == "Michiru": # リオ裏ミチル
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    else:
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア

    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Michiru")  # ミチル → ハナコ
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ -> ハナコ

    # フェーズ移行
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    print(state.cards)
    if state.cards[0] == "Hikari": # ヒカリ裏セイア
        state = sim.play_by_name("Rio_Copy")  # Cハナコ
        state = sim.play_by_name("Hikari")  # ヒカリ
    else:
        state = sim.play_by_name("Hikari")  # ヒカリ
        state = sim.play_by_name("Rio_Copy")  # Cハナコ


    state = sim.play_by_name("Michiru")  # ミチル

    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    return state.cards


def test_case3(members) -> None:

    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_case1_tl(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")


def test_case4_tl(initial_cards: tuple[str, ...]) -> tuple[str, ...]:
    sim = build_simulator()
    state = sim.initialize_state(initial_cards)

    init_state = state
    state = sim.play_by_name("Hikari")  # ヒカリ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ → ハナコ

    state = sim.play_by_name("Rio_Copy")  # Cハナコ
    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        state = sim.play_by_name("Seia")  # セイア

        state = sim.play_by_name("Aru")  # アル
    elif init_state.cards[3] == "Michiru": # リオ裏ミチル
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    else:
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア

    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Michiru")  # ミチル → ハナコ
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ -> ハナコ

    # フェーズ移行
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    print(state.cards)
    if state.cards[0] == "Hikari": # ヒカリ裏セイア
        state = sim.play_by_name("Rio_Copy")  # Cハナコ
        state = sim.play_by_name("Hikari")  # ヒカリ
    else:
        state = sim.play_by_name("Hikari")  # ヒカリ
        state = sim.play_by_name("Rio_Copy")  # Cハナコ


    state = sim.play_by_name("Michiru")  # ミチル

    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    return state.cards


def test_case4(members) -> None:

    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_case4_tl(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")


def test_case56_tl(initial_cards: tuple[str, ...]) -> tuple[str, ...]:
    sim = build_simulator()
    state = sim.initialize_state(initial_cards)

    init_state = state
    state = sim.play_by_name("Hikari")  # ヒカリ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ → ハナコ

    state = sim.play_by_name("Rio_Copy")  # Cハナコ
    if init_state.cards[3] == "Seia": # ヒカリ裏セイア
        state = sim.play_by_name("Seia")  # セイア
        state = sim.play_by_name("Aru")  # アル
    elif init_state.cards[3] == "Michiru": # リオ裏ミチル
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア
    else:
        state = sim.play_by_name("Aru")  # アル
        state = sim.play_by_name("Seia")  # セイア

    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Michiru")  # ミチル → ハナコ
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    state = sim.play_by_name("Rio", target="Hanako_Swimsuit")  # リオ -> ハナコ

    # フェーズ移行
    state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    print(state.cards)
    if state.cards[0] == "Hikari": # ヒカリ裏セイア
        state = sim.play_by_name("Rio_Copy")  # Cハナコ
        state = sim.play_by_name("Hikari")  # ヒカリ
    else:
        state = sim.play_by_name("Hikari")  # ヒカリ
        state = sim.play_by_name("Rio_Copy")  # Cハナコ


    state = sim.play_by_name("Michiru")  # ミチル

    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ
    # state = sim.play_by_name("Hanako_Swimsuit")  # ハナコ

    return state.cards


def test_case5(members) -> None:
    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_case56_tl(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")

def test_case6(members) -> None:

    # 前半3つ（固定）と後半3つ（ターゲット）に分ける
    fixed_part = members[:3]
    target_part = members[3:]

    # 後ろ3つの順列を生成し、固定部分と合体させる
    # itertools.permutations はイテレータを返すので、そのままループ回せます
    for p in itertools.permutations(target_part):
        # タプル同士を足して、全メンバーの新しい並びを作成
        full_sequence = fixed_part + p
        try:
            print(full_sequence, "->", test_case56_tl(full_sequence))
        except Exception as e:
            print(f"Error occurred with {full_sequence}: {e}")

# test(members=("Hikari", "Seia", "Rio", "Hanako_Swimsuit", "Aru", "Michiru"))  # case1
# test(members=("Rio", "Hikari", "Seia", "Hanako_Swimsuit", "Aru", "Michiru"))  # case2
# test(members=("Hikari", "Rio", "Seia", "Hanako_Swimsuit", "Aru", "Michiru"))  # case3
# test(members=("Seia", "Rio", "Hikari", "Hanako_Swimsuit", "Aru", "Michiru"))  # case4
# test(members=("Rio", "Seia", "Hikari", "Hanako_Swimsuit", "Aru", "Michiru"))  # case5
# test(members=("Seia", "Hikari", "Rio", "Hanako_Swimsuit", "Aru", "Michiru"))  # case6


# test_case1(members=("Aru", "Rio", "Hikari", "Seia", "Michiru", "Hanako_Swimsuit"))  # case1 5/6
# test_case2(members=("Hikari", "Aru", "Rio", "Seia", "Michiru","Hanako_Swimsuit"))  # case2 4/6
test_case3(members=( "Aru", "Hikari", "Rio", "Seia", "Michiru","Hanako_Swimsuit"))  # case3 5/6
# test_case4(members=("Hikari", "Rio", "Aru", "Seia", "Michiru","Hanako_Swimsuit"))  # case4 4/6
# test_case5(members=("Rio", "Hikari", "Aru", "Seia", "Michiru","Hanako_Swimsuit"))  # case5 4/6
# test_case6(members=("Rio", "Aru", "Hikari", "Seia", "Michiru","Hanako_Swimsuit"))  # case6 4/6
