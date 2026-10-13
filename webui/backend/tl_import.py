"""
ラフに書かれたTL(どの生徒のEXをどの順で、誰を対象に使うか)をシミュレータで実行し、
webuiの共有リンク(#share=)として読み込める形に変換する処理。

ラフな表記(「Cイロハ」「リオ → イロハ」等)の解釈自体は呼び出し側(LLM)に任せ、
ここでは「正規化済みの手順列を厳密に実行し、破綻したらどこで何が起きたかを返す」ことに徹する。
MCPサーバー(mcp_server.py)から呼ばれるが、MCPには依存しない。
"""

from __future__ import annotations

import base64
import difflib
import gzip
import itertools
import json
import os
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State
from webui.backend.catalog import (
    BUILTINS,
    build_specs,
    play_and_record,
    state_to_dict,
)

DEFAULT_BASE_URL = "http://localhost:8000/"
# 初期順の総当りは n! 通りになるため、現実的な時間で終わる枚数に制限する
MAX_PERMUTATION_CARDS = 8


@dataclass
class Step:
    card: str  # 使用する生徒(キー or 表示名)。スロットで指定する場合は空でよい
    target: str = ""  # 対象(リオのコピー先、イブキのお友達はカンマ区切り等)
    slot: Optional[int] = None  # 手札スロットを明示する場合(0始まり)
    note: str = ""  # 時刻・メモ等。webuiのコメント欄に入る


class TLError(ValueError):
    """入力そのものが不正(未知の生徒名など)で、実行に進めない場合のエラー"""


# ---------------------------------------------------------------------------
# 名前解決
# ---------------------------------------------------------------------------


def _normalize(name: str) -> str:
    # 全角括弧・全角英数を半角に寄せ、空白を除いて比較する
    return "".join(unicodedata.normalize("NFKC", name).split()).lower()


def _build_name_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    for key, entry in BUILTINS.items():
        index[_normalize(key)] = key
        index.setdefault(_normalize(entry.label), key)
    # 手札上でのみ現れるトークン(リオのコピー)
    index.setdefault(_normalize("Rio_Copy"), "Rio_Copy")
    return index


_NAME_INDEX = _build_name_index()


def resolve_name(name: str) -> str:
    """キー(Hanako_Swimsuit)または表示名(ハナコ(水着))をキーに解決する。"""
    key = _NAME_INDEX.get(_normalize(name))
    if key is None:
        raise TLError(f"未知の生徒名です: {name!r}{_suggest(name)}")
    return key


def _suggest(name: str) -> str:
    candidates = difflib.get_close_matches(
        _normalize(name), list(_NAME_INDEX), n=5, cutoff=0.4
    )
    if not candidates:
        return ""
    keys = dict.fromkeys(_NAME_INDEX[c] for c in candidates)
    return " (候補: " + ", ".join(f"{k}={BUILTINS[k].label}" for k in keys if k in BUILTINS) + ")"


def _resolve_target(target: str) -> str:
    # イブキ(水着)のお友達指定のようにカンマ区切りで複数指定されることがある
    names = [t for t in (s.strip() for s in target.replace("、", ",").split(",")) if t]
    return ",".join(resolve_name(t) for t in names)


def list_characters(query: str = "") -> List[Dict[str, Any]]:
    """生徒カタログを返す。queryはキー・表示名への部分一致(正規化後)で絞り込む。"""
    q = _normalize(query)
    result = []
    for key, entry in BUILTINS.items():
        if q and q not in _normalize(key) and q not in _normalize(entry.label):
            continue
        result.append(
            {
                "key": key,
                "label": entry.label,
                "role": entry.role,
                "cost": entry.cost,
                "extra_cost": entry.extra_cost,
                "needs_target": _initially_needs_target(key),
                "custom_spec": entry.spec.__name__ != "GenericSpec",
            }
        )
    return result


def _initially_needs_target(key: str) -> bool:
    # 編成前の一覧なので、初期状態(イブキ(水着)ならお友達未指定のEX1)で使う場合の宣言を見る
    spec = build_specs([key])[0]
    return spec.target_input(State(cards=(key,))).required


# ---------------------------------------------------------------------------
# 実行
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    characters: List[str]
    hand_size: int
    initial_state: Dict[str, Any]
    history: List[Dict[str, Any]]
    current_state: Dict[str, Any]
    notes: Dict[int, str]  # step番号(1始まり) -> メモ
    error: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _find_slot(sim: Simulator, card: str) -> Optional[int]:
    hand = sim.state.hand
    if card in hand:
        return hand.index(card)
    # リオ(コピー)のような代理カードは、元の生徒名で指定されても使えるようにする
    # (ラフTLでは「リオ → イロハ」の後に単に「リオ」と書かれるため)
    for slot, name in enumerate(hand):
        spec = sim.registry.get(name) if name else None
        if spec and spec.is_proxy and spec.get_discard_transform(sim.state) == card:
            return slot
    return None


def normalize_inputs(
    characters: Iterable[str], steps: Iterable[Step], hand_size: int
) -> Tuple[List[str], List[Step]]:
    """名前解決と入力検証を行う。問題があれば TLError。"""
    keys = [resolve_name(c) for c in characters]
    duplicated = sorted({k for k in keys if keys.count(k) > 1})
    if duplicated:
        raise TLError(f"編成に同じ生徒が重複しています: {duplicated}")
    if hand_size < 1:
        raise TLError("hand_size は1以上が必要です")
    if len(keys) <= hand_size:
        raise TLError(f"デッキにカードが必要です (総数 {len(keys)} > hand_size={hand_size})")

    resolved_steps = []
    for i, step in enumerate(steps, start=1):
        if not step.card and step.slot is None:
            raise TLError(f"step {i}: card か slot のどちらかが必要です")
        try:
            resolved_steps.append(
                Step(
                    card=resolve_name(step.card) if step.card else "",
                    target=_resolve_target(step.target) if step.target else "",
                    slot=step.slot,
                    note=step.note,
                )
            )
        except TLError as e:
            raise TLError(f"step {i}: {e}") from None
    return keys, resolved_steps


def run_tl(
    characters: List[str],
    steps: List[Step],
    hand_size: int = 3,
    env: Optional[Dict[str, Any]] = None,
    specs: Optional[List[CharacterSpec]] = None,
) -> RunResult:
    """正規化済みの編成(=初期の手札+山札順)と手順列を実行する。

    途中で破綻した場合(使おうとした生徒が手札に無い、対象指定が不正等)は
    そこで止め、それまでの履歴と error を返す。
    specs を省略すると webui と同じ生徒カタログから組み立てる(テストでは差し替える)。
    """
    sim = Simulator(specs if specs is not None else build_specs(characters))
    sim.initialize_state(tuple(characters), env=dict(env or {}), hand_size=hand_size)
    result = RunResult(
        characters=list(characters),
        hand_size=hand_size,
        initial_state=state_to_dict(sim.state),
        history=[],
        current_state=state_to_dict(sim.state),
        notes={},
    )

    for i, step in enumerate(steps, start=1):
        if step.slot is not None:
            if not (0 <= step.slot < hand_size):
                result.error = _error(i, step, sim, f"スロットは0~{hand_size - 1}の範囲です")
                break
            slot = step.slot
            if step.card and sim.state.hand[slot] != step.card and _find_slot(sim, step.card) != slot:
                result.error = _error(
                    i, step, sim, f"スロット{slot}は {sim.state.hand[slot]} で、{step.card} ではありません"
                )
                break
        else:
            slot = _find_slot(sim, step.card)
            if slot is None:
                result.error = _error(i, step, sim, f"{step.card} は手札にありません")
                break

        note = step.note
        if not step.target and _needs_target(sim, sim.state.hand[slot]):
            # 対象未指定でも実行はできるが、ほぼ確実に書き漏れなので警告として残す
            note = (note + " " if note else "") + "[警告: 対象未指定]"

        try:
            entry = play_and_record(sim, slot, step.target, result.history)
        except Exception as e:  # spec側のValueError等(対象指定の不正など)
            result.error = _error(i, step, sim, str(e))
            break
        result.history.append(entry)
        if note:
            result.notes[i] = note

    result.current_state = state_to_dict(sim.state)
    return result


def _needs_target(sim: Simulator, card: str) -> bool:
    # 対象が必須かは各Specの宣言(target_input)に従う。イブキ(水着)のEX1/EX2のように
    # 状態で変わるものがあるため「今」の状態で判定する(アリス(臨戦)は未指定 = 敵対象で必須ではない)
    spec = sim.registry.get(card)
    return spec is not None and spec.target_input(sim.state).required


def _error(index: int, step: Step, sim: Simulator, reason: str) -> Dict[str, Any]:
    return {
        "step": index,
        "card": step.card,
        "target": step.target,
        "reason": reason,
        "hand": list(sim.state.hand),
        "deck": list(sim.state.deck),
        "env": state_to_dict(sim.state)["env"],
    }


def find_initial_orders(
    characters: List[str],
    steps: List[Step],
    hand_size: int = 3,
    env: Optional[Dict[str, Any]] = None,
    max_results: int = 10,
) -> Dict[str, Any]:
    """手順列と矛盾しない初期の手札+山札順を総当りで探す。

    手札内の並び順はサイクルに影響しない(使ったスロットに補充されるだけ)ため、
    スロット指定が無い限り手札部分は集合として扱い、重複する並びは除いて数える。
    一つも完走しない場合は、最も先まで進めた並びを返す(TLのどこが怪しいかの手掛かり)。
    """
    if len(characters) > MAX_PERMUTATION_CARDS:
        raise TLError(
            f"総当りは{MAX_PERMUTATION_CARDS}枚までです (指定: {len(characters)}枚)。"
            "初期手札や山札の一部が分かっていれば、それを固定して simulate_tl で確認してください。"
        )

    slot_sensitive = any(step.slot is not None for step in steps)
    seen = set()
    matches: List[List[str]] = []
    total_matches = 0
    best_progress = -1
    best: List[Dict[str, Any]] = []

    for perm in itertools.permutations(characters):
        canonical = perm if slot_sensitive else (frozenset(perm[:hand_size]), perm[hand_size:])
        if canonical in seen:
            continue
        seen.add(canonical)

        result = run_tl(list(perm), steps, hand_size, env)
        if result.ok:
            total_matches += 1
            if len(matches) < max_results:
                matches.append(list(perm))
            continue
        progress = result.error["step"] - 1
        if progress > best_progress:
            best_progress, best = progress, []
        if progress == best_progress and len(best) < max_results:
            best.append({"order": list(perm), "error": result.error})

    if total_matches:
        return {"total_matches": total_matches, "orders": matches}
    return {
        "total_matches": 0,
        "orders": [],
        "best_partial": {"completed_steps": best_progress, "candidates": best},
    }


# ---------------------------------------------------------------------------
# webui連携(共有リンク / エクスポートファイル)
# ---------------------------------------------------------------------------


def build_save(result: RunResult, name: str) -> Dict[str, Any]:
    """webuiのセーブデータ形式(loadSaveが受け取る形)に変換する。"""
    # webuiのコメント欄は「フレームN」(N=0が初期状態)に付き、フレームNには
    # step N+1 の行動が表示されるため、step i のメモはフレーム i-1 に置く
    frame_comments = {str(step - 1): note for step, note in result.notes.items()}
    if result.error:
        frame_comments[str(len(result.history))] = (
            f"[MCP取込: step {result.error['step']} で停止] {result.error['reason']}"
        )
    return {
        "name": name,
        "characters": result.characters,
        "hand_size": result.hand_size,
        "initial_state": result.initial_state,
        "current_state": result.current_state,
        "history": result.history,
        "frame_comments": frame_comments,
    }


def encode_share(save: Dict[str, Any]) -> str:
    """webuiの encodeShareData と同じ形式('z' + base64url(gzip(JSON)))にする。"""
    raw = json.dumps(save, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(gzip.compress(raw)).decode("ascii").rstrip("=")
    return "z" + encoded


def share_url(save: Dict[str, Any], base_url: Optional[str] = None) -> str:
    base = base_url or os.environ.get("EXSIM_BASE_URL") or DEFAULT_BASE_URL
    return base.split("#")[0] + "#share=" + encode_share(save)

