"""ボタン操作の冪等性(開発指針 0-5)。

端末は操作ごとに一意の request_id を送る。
- 初めての request_id: 操作を行い、要求の内容と応答を api_requests に記録する
- 同じ request_id で同じ内容: 操作はせず、最初の応答をそのまま返す
- 同じ request_id で違う内容: 拒否する(409)
- ルール違反で失敗した操作は記録しない(同じ request_id で送り直せば、もう一度判定する)

本アプリは1プロセスで動かす前提(開発指針 0-7)なので、記録の書き込みはプロセス内のロックで1つずつ行う
(終了していない記録の確認と追加の間に、ほかの操作が割り込まないようにする)。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import ApiRequest
from app.services.errors import NotFound, RuleViolation

M = TypeVar("M", bound=BaseModel)

_write_lock = threading.Lock()

REQUEST_ID_REUSED = "同じリクエストIDで、内容の異なる操作が送られました。画面を更新してから、もう一度操作してください"
CONCURRENT_CONFLICT = "ほかの操作と同時に行われたため、記録できませんでした。画面を更新してから、もう一度操作してください"


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _replay(existing: ApiRequest, operation: str, payload: str, model: type[M]) -> M:
    if existing.operation != operation or existing.payload != payload:
        raise RuleViolation(REQUEST_ID_REUSED)
    return model.model_validate_json(existing.response)


def run_idempotent(
    session: Session,
    request_id: str,
    operation: str,
    payload: dict,
    model: type[M],
    action: Callable[[datetime], M],
) -> M:
    """action(now) を1回だけ行う。action は記録を追加して応答を返す(コミットはここで行う)。"""
    body = _dump(payload)
    with _write_lock:
        existing = session.get(ApiRequest, request_id)
        if existing is not None:
            return _replay(existing, operation, body, model)

        now = clock.now()
        try:
            result = action(now)
            session.add(ApiRequest(
                request_id=request_id, operation=operation, payload=body,
                response=result.model_dump_json(), created_at=now,
            ))
            session.commit()
        except (RuleViolation, NotFound):
            session.rollback()
            raise
        except IntegrityError:
            # DBの一意制約に当たった(同じ request_id の同時送信や、終了していない記録の二重追加など)
            session.rollback()
            existing = session.get(ApiRequest, request_id)
            if existing is not None:
                return _replay(existing, operation, body, model)
            raise RuleViolation(CONCURRENT_CONFLICT) from None
        except Exception:
            session.rollback()
            raise
        return result
