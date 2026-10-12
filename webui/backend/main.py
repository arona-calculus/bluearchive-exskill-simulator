"""
BA EX Skill Simulator - FastAPI Backend

起動方法:
  cd bluearchive-exskill-simulator
  uv run --extra webui uvicorn webui.backend.main:app --reload --port 8000
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.spec import CharacterSpec
from ba_exsim.core.state import State
from ba_exsim.specs.alice_battle import AliceBattleSpec
from ba_exsim.specs.generic import GenericSpec
from ba_exsim.specs.hanako_swimsuit import HanakoSwimsuitSpec
from ba_exsim.specs.ibuki_swimsuit import IbukiSwimsuitSpec
from ba_exsim.specs.rio import RioCopySpec, RioSpec

app = FastAPI(title="BA ExSkill Simulator API", root_path="/exsim")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, Dict] = {}


class BuiltinEntry(NamedTuple):
    label: str
    spec: type
    role: Optional[str] = None  # "STRIKER" / "SPECIAL" (character_library由来、不明ならNone)
    cost: Optional[int] = None  # EXスキル消費コスト(lv5時点、character_library由来、不明ならNone)
    extra_cost: Optional[int] = None  # 変身後スキル(ExtraSkills)の消費コスト。無いキャラはNone


BUILTINS: Dict[str, BuiltinEntry] = {
    "Alice_Battle":    BuiltinEntry("アリス(臨戦)", AliceBattleSpec),
    "Aru":             BuiltinEntry("アル",         GenericSpec),
    "Aru_Dress":       BuiltinEntry("アル(ドレス)",   GenericSpec),
    "Eri":             BuiltinEntry("エリ",           GenericSpec),
    "Kayoko_Newyear":  BuiltinEntry("カヨコ(正月)",    GenericSpec),
    "Kisaki":          BuiltinEntry("キサキ",         GenericSpec),
    "Key":             BuiltinEntry("ケイ",           GenericSpec),
    "Shiroko_Swimsuit":  BuiltinEntry("シロコ(水着)",   GenericSpec),
    "Seia":            BuiltinEntry("セイア",         GenericSpec),
    "Seia_Swimsuit":   BuiltinEntry("セイア(水着)",   GenericSpec),
    "Hanako_Swimsuit": BuiltinEntry("ハナコ(水着)",   HanakoSwimsuitSpec),
    "Hare_Camp":       BuiltinEntry("ハレ(キャンプ)", GenericSpec),
    "Hikari":          BuiltinEntry("ヒカリ",         GenericSpec),
    "Nagisa":          BuiltinEntry("ナギサ",         GenericSpec),
    "Nagisa_Swimsuit": BuiltinEntry("ナギサ(水着)",   GenericSpec),
    "Michiru_Dress":   BuiltinEntry("ミチル(ドレス)", GenericSpec),
    "Hoshino":         BuiltinEntry("ホシノ",         GenericSpec),
    "Hoshino_Swimsuit":BuiltinEntry("ホシノ(水着)",   GenericSpec),
    "Hoshino_Battle_Attack": BuiltinEntry("ホシノ(臨戦)[攻撃型]",   GenericSpec),
    "Hoshino_Battle_Defence": BuiltinEntry("ホシノ(臨戦)[防御型]",   GenericSpec),
    "Ibuki_Swimsuit":  BuiltinEntry("イブキ(水着)",     IbukiSwimsuitSpec),
    "Mine":            BuiltinEntry("ミネ",           GenericSpec),
    "Miyako":          BuiltinEntry("ミヤコ",         GenericSpec),
    "Miyako_Swimsuit": BuiltinEntry("ミヤコ(水着)",   GenericSpec),
    "Rio":             BuiltinEntry("リオ",          RioSpec),
}

_LIBRARY_PATH = Path(__file__).parent / "character_library" / "data" / "characters.json"


def _load_generated_builtins() -> Dict[str, BuiltinEntry]:
    """character_library/build_library.py が生成したキャラライブラリを読み込む。
    未実装の生徒は GenericSpec を割り当てる(固有のEXスキル実装が必要な生徒は
    上の BUILTINS に手動で追記し、専用の Spec クラスを割り当てること)。
    """
    if not _LIBRARY_PATH.exists():
        return {}
    with _LIBRARY_PATH.open(encoding="utf-8") as f:
        entries = json.load(f)
    return {
        e["key"]: BuiltinEntry(
            e["label"], GenericSpec,
            role=e.get("role"), cost=e.get("ex_cost_max"), extra_cost=e.get("ex_extra_cost_max"),
        )
        for e in entries
        if e.get("key") and e.get("label")
    }


# 手動でカスタムSpecを割り当てた上のエントリを優先し、生成分で不足を補う
_GENERATED_BUILTINS = _load_generated_builtins()
BUILTINS = {**_GENERATED_BUILTINS, **BUILTINS}

# 手動定義24件にはrole/costが無いため、生成データ側から補完する
for _key, _entry in list(BUILTINS.items()):
    if _key in _GENERATED_BUILTINS:
        _generated_entry = _GENERATED_BUILTINS[_key]
        BUILTINS[_key] = _entry._replace(
            role=_entry.role if _entry.role is not None else _generated_entry.role,
            cost=_entry.cost if _entry.cost is not None else _generated_entry.cost,
            extra_cost=_entry.extra_cost if _entry.extra_cost is not None else _generated_entry.extra_cost,
        )

NEEDS_TARGET: List[str] = ["Rio", "Alice_Battle", "Ibuki_Swimsuit"]


def build_specs(characters: List[str]) -> List[CharacterSpec]:
    specs: List[CharacterSpec] = []
    seen: set = set()
    character_roles = {
        name: BUILTINS[name].role
        for name in characters
        if name in BUILTINS and BUILTINS[name].role
    }
    for name in characters:
        if name in seen:
            continue
        seen.add(name)
        if name in BUILTINS:
            entry = BUILTINS[name]
            spec_cls = entry.spec
            if spec_cls is GenericSpec:
                specs.append(spec_cls(name, cost=entry.cost))
            elif spec_cls is IbukiSwimsuitSpec:
                specs.append(spec_cls(
                    character_roles=character_roles, cost=entry.cost, extra_cost=entry.extra_cost,
                ))
            else:
                specs.append(spec_cls(cost=entry.cost))
        else:
            specs.append(GenericSpec(name))
    if "Rio" in seen:
        specs.append(RioCopySpec())
    return specs


def state_to_dict(state) -> Dict[str, Any]:
    return {
        "hand": list(state.hand),
        "deck": list(state.deck),
        "env": {k: v for k, v in state.env.items() if v is not None},
    }


class SessionCreate(BaseModel):
    characters: List[str]
    hand_size: int = 3
    env: Optional[Dict[str, Any]] = None
    # セーブデータからの復元用
    restore_current: Optional[Dict[str, Any]] = None
    restore_initial: Optional[Dict[str, Any]] = None
    restore_history: Optional[List[Dict[str, Any]]] = None


class RewindRequest(BaseModel):
    frame: int  # 0 = 初期状態, N = step N 実行後の状態


class PlayRequest(BaseModel):
    slot: int
    target: str = ""


@app.get("/api/specs")
def get_specs():
    # 生徒固有の表示(ゲージ等の状態バッジ、リオ(コピー)等のカード)は各Specの宣言から集める。
    # フロントエンドはこれを汎用的に描画するだけで、生徒ごとの分岐を持たない
    spec_classes = {entry.spec for entry in BUILTINS.values()}
    return {
        "builtin": [
            {"value": k, "label": v.label, "role": v.role}
            for k, v in BUILTINS.items()
        ],
        "needs_target": NEEDS_TARGET,
        "env_displays": {d.key: asdict(d) for cls in spec_classes for d in cls.ENV_DISPLAYS},
        "card_displays": {d.card: asdict(d) for cls in spec_classes for d in cls.CARD_DISPLAYS},
    }


@app.get("/api/icons")
def get_icons():
    icons_dir = Path(__file__).parent.parent / "assets" / "icons"
    if not icons_dir.exists():
        return {"available": []}
    return {"available": [p.stem for p in sorted(icons_dir.glob("*.png"))]}


@app.post("/api/session")
def create_session(body: SessionCreate):
    if body.hand_size < 1:
        raise HTTPException(status_code=400, detail="hand_size は1以上が必要です")
    if len(body.characters) <= body.hand_size:
        raise HTTPException(status_code=400, detail=f"デッキにカードが必要です (総数 > hand_size={body.hand_size})")

    specs = build_specs(body.characters)
    sim = Simulator(specs)

    if body.restore_current:
        # セーブデータからの復元: まず仮初期化してからstateを上書き
        sim.initialize_state(tuple(body.characters), env={}, hand_size=body.hand_size)
        cards = tuple(body.restore_current["hand"] + body.restore_current["deck"])
        sim.state = State(cards=cards, env=body.restore_current.get("env", {}), hand_size=body.hand_size)
        initial_state = body.restore_initial or state_to_dict(sim.state)
        history = body.restore_history or []
    else:
        state = sim.initialize_state(tuple(body.characters), env=body.env or {}, hand_size=body.hand_size)
        initial_state = state_to_dict(state)
        history = []

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "sim": sim,
        "characters": body.characters,
        "hand_size": body.hand_size,
        "initial_state": initial_state,
        "history": history,
    }
    return {
        "session_id": session_id,
        "state": state_to_dict(sim.state),
        "characters": body.characters,
        "hand_size": body.hand_size,
        "initial_state": initial_state,
        "history": history,
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    session = sessions[session_id]
    sim = session["sim"]
    hand_size = session["hand_size"]
    return {
        "session_id": session_id,
        "state": state_to_dict(sim.state),
        "characters": session["characters"],
        "hand_size": hand_size,
        "initial_state": session["initial_state"],
        "history": session["history"],
    }


@app.get("/api/session/{session_id}/target_input/{slot}")
def get_target_input(session_id: str, slot: int):
    """手札スロットslotのカードを「今」使う場合の対象指定の形式(CharacterSpec.target_input)"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    sim = sessions[session_id]["sim"]
    if not (0 <= slot < sim.state.hand_size):
        raise HTTPException(status_code=400, detail=f"スロットは0~{sim.state.hand_size - 1}の範囲です")
    spec = sim.registry.get(sim.state.cards[slot])
    if spec is None:
        raise HTTPException(status_code=400, detail="スロットにカードがありません")
    return asdict(spec.target_input(sim.state))


@app.post("/api/session/{session_id}/play")
def play_card(session_id: str, body: PlayRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    session = sessions[session_id]
    sim = session["sim"]
    hand_size = session["hand_size"]

    if not (0 <= body.slot < hand_size):
        raise HTTPException(status_code=400, detail=f"スロットは0~{hand_size - 1}の範囲です")

    state_before = state_to_dict(sim.state)
    played_card = sim.state.cards[body.slot]

    # コストはプレイ前のstateに対して評価する(リオ(コピー)はapply_effect自身が
    # rio_copy_targetをクリアするため、プレイ後では参照できなくなるキャラがいる)
    spec = sim.registry.get(played_card)
    step_cost = spec.get_cost(sim.state) if spec else None

    try:
        new_state = sim.play(body.slot, target=body.target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    prev_cumulative_cost = session["history"][-1]["cumulative_cost"] if session["history"] else 0
    cumulative_cost = prev_cumulative_cost + (step_cost or 0)

    entry = {
        "step": len(session["history"]) + 1,
        "card": played_card,
        "slot": body.slot,
        "target": body.target,
        "state_before": state_before,
        "state_after": state_to_dict(new_state),
        "cost": step_cost,
        "cumulative_cost": cumulative_cost,
    }
    session["history"].append(entry)
    return {
        "state": state_to_dict(new_state),
        "history": session["history"],
        "played_card": played_card,
    }


@app.post("/api/session/{session_id}/rewind")
def rewind_session(session_id: str, body: RewindRequest):
    """指定フレームの状態に巻き戻す (frame=0: 初期状態, frame=N: step N 実行後)"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    session = sessions[session_id]
    sim = session["sim"]
    hand_size = session["hand_size"]
    history = session["history"]

    if body.frame == 0:
        s = session["initial_state"]
        new_history = []
    elif 1 <= body.frame <= len(history):
        s = history[body.frame - 1]["state_after"]
        new_history = history[:body.frame]
    else:
        raise HTTPException(status_code=400, detail="無効なフレーム番号です")

    cards = tuple(s["hand"] + s["deck"])
    sim.state = State(cards=cards, env=s.get("env", {}), hand_size=hand_size)
    session["history"] = new_history

    return {
        "state": state_to_dict(sim.state),
        "history": new_history,
        "initial_state": session["initial_state"],
    }


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    sessions.pop(session_id, None)
    return {"ok": True}


_assets_dir = Path(__file__).parent.parent / "assets"
_icons_dir = _assets_dir / "icons"


@app.get("/assets/icons/{filename}")
def serve_icon(filename: str):
    file_path = (_icons_dir / filename).resolve()
    if not str(file_path).startswith(str(_icons_dir.resolve())):
        raise HTTPException(status_code=403)
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    # アイコンは差し替えが起こり得るため、ブラウザキャッシュを毎回検証させる
    # (ETag/Last-Modifiedによりコンテンツが変わっていなければ304で済む)
    return FileResponse(file_path, headers={"Cache-Control": "no-cache"})


_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
