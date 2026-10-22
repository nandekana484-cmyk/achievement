"""APIが返す形(Pydantic のモデル)と、DBの行からの組み立て。

冪等性のため、操作の応答はこの形のまま api_requests に保存し、再送にはそれを返す。
時刻はすべて日本時間(+09:00)付き。中身は責務ごとのモジュールに分け、ここから同じ名前で使えるようにする。
"""

from app.services.views.corrections import (
    CorrectionChangeOut,
    CorrectionOut,
    LineEventCorrectionResultOut,
    RunCorrectionResultOut,
    correction_out,
)
from app.services.views.line_events import (
    LineEventOut,
    line_event_out,
)
from app.services.views.masters import (
    EquipmentOut,
    LineOut,
    MastersOut,
    OperatorOut,
    ReasonOut,
    line_out,
)
from app.services.views.operators import (
    CurrentOperatorOut,
    current_operator_out,
    operator_name,
    worker_id_of,
)
from app.services.views.runs import (
    LotOut,
    NgEntryOut,
    NgInputOut,
    RunCompletionOut,
    RunEventOut,
    RunInputOut,
    StepResultOut,
    ng_entry_out,
    ng_input_out,
    run_completion_out,
    run_event_out,
    run_input_out,
)

__all__ = [
    "correction_out",
    "CorrectionChangeOut",
    "CorrectionOut",
    "LineEventCorrectionResultOut",
    "RunCorrectionResultOut",
    "current_operator_out",
    "CurrentOperatorOut",
    "EquipmentOut",
    "line_event_out",
    "line_out",
    "LineEventOut",
    "LineOut",
    "LotOut",
    "MastersOut",
    "ng_entry_out",
    "ng_input_out",
    "NgEntryOut",
    "NgInputOut",
    "operator_name",
    "OperatorOut",
    "ReasonOut",
    "run_completion_out",
    "run_event_out",
    "run_input_out",
    "RunCompletionOut",
    "RunEventOut",
    "RunInputOut",
    "StepResultOut",
    "worker_id_of",
]
