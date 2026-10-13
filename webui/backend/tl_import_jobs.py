"""
webuiのTL取り込みページのジョブ管理と利用制限。

Claude の解釈には数十秒〜数分かかるため、取り込みはジョブとして別スレッドで実行し、
ページは進捗をポーリングする(リバースプロキシの読み取りタイムアウトにもかからない)。
APIキーはサーバーの持ち主のものを全利用者で共有するため、入力の長さ・IPごとの回数・
1日の総数・同時実行数に上限を設ける。状態はプロセス内にしか持たない(uvicornのワーカー1つが前提)。
リバースプロキシの後ろでは、uvicorn を --proxy-headers 付きで起動しないとIPごとの制限が全員共通になる。
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

import anthropic

from webui.backend import tl_agent

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


MAX_CHARS = _env_int("EXSIM_TL_IMPORT_MAX_CHARS", 6000)
PER_IP_PER_HOUR = _env_int("EXSIM_TL_IMPORT_PER_IP_PER_HOUR", 10)
PER_DAY = _env_int("EXSIM_TL_IMPORT_PER_DAY", 100)
MAX_CONCURRENT = _env_int("EXSIM_TL_IMPORT_MAX_CONCURRENT", 2)
JOB_TTL_SECONDS = 3600

Runner = Callable[..., tl_agent.ImportResult]


def enabled() -> bool:
    """APIキーが設定されているサーバーでだけ取り込みを有効にする。"""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class LimitError(Exception):
    """受け付けられない取り込み(入力不正・回数制限)。status はそのままHTTPステータスにする。"""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class JobStore:
    def __init__(self, runner: Optional[Runner] = None):
        # テストでは Claude を呼ばない runner に差し替える
        self._runner = runner or tl_agent.import_rough_tl
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._ip_hits: Dict[str, Deque[float]] = {}
        self._day: Optional[datetime.date] = None
        self._day_count = 0
        self._running = 0

    def submit(self, tl_text: str, notes: str, ip: str) -> str:
        if not tl_text.strip():
            raise LimitError(400, "TLが空です。")
        if len(tl_text) + len(notes) > MAX_CHARS:
            raise LimitError(400, f"TLと補足は合わせて{MAX_CHARS}文字までです。")

        now = time.time()
        with self._lock:
            self._drop_old_jobs(now)
            if self._running >= MAX_CONCURRENT:
                raise LimitError(429, "ほかの取り込みを実行中です。少し待ってから試してください。")
            today = datetime.date.today()
            if self._day != today:
                self._day, self._day_count = today, 0
            if self._day_count >= PER_DAY:
                raise LimitError(429, "本日の取り込み回数の上限に達しました。")
            hits = self._ip_hits.setdefault(ip, deque())
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= PER_IP_PER_HOUR:
                raise LimitError(429, f"取り込みは1時間に{PER_IP_PER_HOUR}回までです。")

            # 失敗した取り込みも数える(APIは呼んでいるため)
            hits.append(now)
            self._day_count += 1
            self._running += 1
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = {
                "status": "running",
                "progress": [],
                "result": None,
                "error": None,
                "created": now,
            }

        threading.Thread(target=self._run, args=(job_id, tl_text, notes), daemon=True).start()
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {k: (list(v) if k == "progress" else v) for k, v in job.items() if k != "created"}

    def _run(self, job_id: str, tl_text: str, notes: str) -> None:
        job = self._jobs[job_id]

        def on_progress(message: str) -> None:
            with self._lock:
                if not job["progress"] or job["progress"][-1] != message:
                    job["progress"].append(message)

        result: Optional[Dict[str, Any]] = None
        error: Optional[str] = None
        try:
            r = self._runner(tl_text, notes, on_progress=on_progress)
            result = {
                "summary": r.summary,
                "simulated": r.simulated,
                "ok": r.ok,
                "error": r.error,
                "share": r.share,
            }
        except tl_agent.TLImportError as e:
            error = str(e)
        except anthropic.AuthenticationError:
            logger.exception("TL取り込み: APIキーが無効")
            error = "サーバーのAPIキーが無効です。管理者に連絡してください。"
        except anthropic.RateLimitError:
            error = "Claude APIが混み合っています。少し待ってから試してください。"
        except anthropic.APIStatusError as e:
            logger.exception("TL取り込み: APIエラー")
            error = f"Claude APIの呼び出しに失敗しました({e.status_code})。"
        except anthropic.APIConnectionError:
            logger.exception("TL取り込み: 接続エラー")
            error = "Claude APIに接続できませんでした。"
        except Exception:
            logger.exception("TL取り込み: 予期しないエラー")
            error = "予期しないエラーが起きました。"
        finally:
            with self._lock:
                job["result"] = result
                job["error"] = error
                job["status"] = "done" if error is None else "error"
                self._running -= 1

    def _drop_old_jobs(self, now: float) -> None:
        for job_id in [j for j, job in self._jobs.items() if now - job["created"] > JOB_TTL_SECONDS]:
            del self._jobs[job_id]
