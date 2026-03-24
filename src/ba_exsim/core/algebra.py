from __future__ import annotations
import numpy as np
from typing import Tuple, Sequence

# Numbaがインストールされている場合、JITコンパイルによる高速化を準備
try:
    from numba import njit
except ImportError:
    # Numbaがない場合は通常のデコレータとして振る舞う
    def njit(func):
        return func


@njit
def get_cycle_permutation(k: int, L: int) -> np.ndarray:
    """
    スロットkのスキルを使用した際の、長さLの巡回置換 π_k^(L) を置換ベクトルとして生成する。

    数学的定義:
    π_k^(L) = (k, 4, 5, ..., L-1)  ※0-indexedの場合、スロットk, 3, 4, ..., L-1

    Args:
        k: 使用したスキルのスロットインデックス (0, 1, 2)
        L: アクティブなデッキ次元 (6 or 7)
    Returns:
        p: 長さ7の置換ベクトル (p[i] は移動後のスロットiにある元のスロット番号)
    """
    # 初期状態は恒等置換 [0, 1, 2, 3, 4, 5, 6]
    p = np.arange(7)

    # 手札スロットkには、山札の先頭(index 3)が入る
    # 山札の各要素は一つずつ前に詰められ、最後尾(index L-1)に使用したkが入る
    # この一連の動きをインデックスの写像として記述
    target_indices = [k] + list(range(3, L))
    # 巡回置換の実行: 3->k, 4->3, 5->4, ..., k->L-1

    temp_val = p[k]
    for i in range(len(target_indices) - 1):
        p[target_indices[i]] = p[target_indices[i + 1]]
    p[target_indices[-1]] = temp_val

    return p


def apply_permutation(cards: Tuple[str, ...], p: np.ndarray) -> Tuple[str, ...]:
    """
    置換ベクトル p を用いて、カードの順列 σ を更新する。
    σ' = σ ∘ p
    """
    # cardsの各要素を置換ベクトルに従って再配置
    # numpy.take を使うことで高速化可能だが、str型なのでリスト内包表記を使用
    return tuple(cards[p[i]] for i in range(len(cards)))


class EXAction:
    """
    EXスキルの発動を、状態空間上の「演算子」としてカプセル化する。
    """

    def __init__(self, slot_index: int):
        if slot_index not in {0, 1, 2}:
            raise ValueError(
                "EXスキルはスロット0, 1, 2のいずれかである必要があります。"
            )
        self.k = slot_index

    def __call__(self, cards: Tuple[str, ...], L: int) -> Tuple[str, ...]:
        """カードの並びに対して置換を作用させる"""
        p = get_cycle_permutation(self.k, L)
        return apply_permutation(cards, p)


# 特殊な作用：恒等写像（ハナコが手札に留まる場合など）
def identity_action(cards: Tuple[str, ...], L: int) -> Tuple[str, ...]:
    return cards
