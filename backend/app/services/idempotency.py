"""ボタン操作の冪等性(開発指針 0-5)。

端末は操作ごとに一意の request_id を送る。
- 初めての request_id: 操作を行い、要求の内容と応答を api_requests に記録する
- 同じ request_id で同じ内容: 操作はせず、最初の応答をそのまま返す
- 同じ request_id で違う内容: 拒否する(409)
- ルール違反やDBの混雑で失敗した操作は記録しない(同じ request_id で送り直せば、もう一度判定する)

操作は write_transaction(app/db/session.py)の中で行う。計画の同期と同じプロセス内のロックを使い、
トランザクションは BEGIN IMMEDIATE で始める(終了していない記録の確認と追加の間に、ほかの書き込みが割り込まない)。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import ApiRequest
from app.db.session import is_busy_error, write_transaction
from app.services.errors import Busy, NotFound, RuleViolation

logger = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

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
    try:
        with write_transaction(session):
            existing = session.get(ApiRequest, request_id)
            if existing is not None:
                result = _replay(existing, operation, body, model)
                session.rollback()
                return result

            now = clock.now()
            result = action(now)
            session.add(ApiRequest(
                request_id=request_id, operation=operation, payload=body,
                response=result.model_dump_json(), created_at=now,
            ))
            session.commit()
            return result
    except (RuleViolation, NotFound):
        session.rollback()
        raise
    except IntegrityError:
        # DBの一意制約に当たった(終了していない記録の二重追加など)。ロックの中なので通常は起きない
        session.rollback()
        with write_transaction(session):
            existing = session.get(ApiRequest, request_id)
            if existing is not None:
                result = _replay(existing, operation, body, model)
                session.rollback()
                return result
        session.rollback()
        raise RuleViolation(CONCURRENT_CONFLICT) from None
    except OperationalError as e:
        session.rollback()
        if is_busy_error(e):
            logger.warning("書き込みが重なったため記録できませんでした(%s): %s", operation, e)
            raise Busy() from e
        raise
    except Exception:
        session.rollback()
        raise
