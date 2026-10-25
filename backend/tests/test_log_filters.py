"""アクセスログに作業者IDなどを残さない(S-13)。詳細: docs/design/security.md"""

from __future__ import annotations

import logging

from app.core.log_filters import MaskAccessLog, mask_query
from app.server import setup_logging


def test_mask_query_hides_only_sensitive_values():
    assert mask_query("/api/operators/lookup?worker_id=K0042") == "/api/operators/lookup?worker_id=***"
    assert mask_query("/x?a=1&WORKER_ID=ａｂ01&b=2") == "/x?a=1&WORKER_ID=***&b=2"
    assert mask_query("/api/plans/search?q=0722&line_code=S") == "/api/plans/search?q=0722&line_code=S"
    assert mask_query("/api/lines/S/board?date=2026-10-21") == "/api/lines/S/board?date=2026-10-21"
    assert mask_query("/api/lines/S/board") == "/api/lines/S/board"


def test_access_log_line_has_no_worker_id(tmp_path):
    setup_logging(tmp_path)
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "10.0.0.5:5000", "GET", "/api/operators/lookup?worker_id=K0042", "1.1", 200)
    for h in logging.getLogger().handlers:
        h.flush()
    text = (tmp_path / "genba.log").read_text(encoding="utf-8")
    assert "worker_id=***" in text and "K0042" not in text
    assert "10.0.0.5" in text  # 接続元は残す(調べるときに要る)


def test_filter_leaves_other_records_alone():
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "hello %s", ("world",), None)
    assert MaskAccessLog().filter(rec) and rec.getMessage() == "hello world"
