"""
BA EX Skill Simulator - FastAPI Backend

起動方法:
  cd bluearchive-exskill-simulator
  uv run --extra webui uvicorn webui.backend.main:app --reload --port 8000

mcp パッケージが入っていれば、リモートMCP(mcp_server.py)も /mcp で同居して公開される。
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ba_exsim.core.simulator import Simulator
from ba_exsim.core.state import State
from webui.backend import tl_import_jobs
from webui.backend.catalog import (
    BUILTINS,
    build_specs,
    play_and_record,
    state_to_dict,
)

try:
    from webui.backend import mcp_server
except ImportError:  # mcp パッケージが無い環境では /mcp を出さないだけにする
    mcp_server = None
    logging.getLogger(__name__).warning("mcp パッケージが無いため、/mcp(リモートMCP)は無効です")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if mcp_server is None:
        yield
        return
    # /mcp のリクエストを捌くために MCP のセッションマネージャーを回しておく
    async with mcp_server.mcp.session_manager.run():
        yield


app = FastAPI(title="BA ExSkill Simulator API", root_path="/exsim", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, Dict] = {}


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

    try:
        entry = play_and_record(sim, body.slot, body.target, session["history"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    session["history"].append(entry)
    return {
        "state": state_to_dict(sim.state),
        "history": session["history"],
        "played_card": entry["card"],
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


# ---------------------------------------------------------------------------
# TL取り込み(import.html): ラフなTLを Claude API で解釈し、共有リンクの形で返す
# ---------------------------------------------------------------------------

tl_jobs = tl_import_jobs.JobStore()

# TL取り込みで使ったトークン数やAPIエラーを、uvicornのログと並べて出す
# (uvicornは自分のロガーにしかハンドラを付けないため、そのままでは INFO が出ない)
_backend_logger = logging.getLogger("webui.backend")
if not _backend_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _backend_logger.addHandler(_handler)
    _backend_logger.setLevel(logging.INFO)


class TLImportRequest(BaseModel):
    tl_text: str
    notes: str = ""


@app.get("/api/tl_import/status")
def tl_import_status():
    return {"enabled": tl_import_jobs.enabled(), "max_chars": tl_import_jobs.MAX_CHARS}


@app.post("/api/tl_import")
def start_tl_import(body: TLImportRequest, request: Request):
    if not tl_import_jobs.enabled():
        raise HTTPException(status_code=503, detail="このサーバーではTL取り込みが無効です(APIキー未設定)")
    ip = request.client.host if request.client else "unknown"
    try:
        job_id = tl_jobs.submit(body.tl_text, body.notes, ip)
    except tl_import_jobs.LimitError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"job_id": job_id}


@app.get("/api/tl_import/{job_id}")
def get_tl_import(job_id: str):
    job = tl_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="取り込みが見つかりません(期限切れの可能性があります)")
    return job


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


if mcp_server is not None:
    # 静的ファイルの "/" より先に登録する(後だと "/" に吸われる)
    app.router.routes.extend(mcp_server.webui_routes())

_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
