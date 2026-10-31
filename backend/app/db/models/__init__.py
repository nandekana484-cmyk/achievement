"""本アプリのDBのテーブル(開発指針 8)。列を変えたら、マイグレーション(app/db/migrations/versions)を追加する。"""

from app.db.models.access import AllowedNetwork
from app.db.models.admin import AdminCredential, AdminLoginAttempt, AdminSession, AuditLog
from app.db.models.exports import ActualsExport, SideLink
from app.db.models.masters import Equipment, Line, Operator, Reason
from app.db.models.plans import (
    PLAN_ACTIVE,
    PLAN_CANCELLED,
    SYNC_ERROR,
    SYNC_GUARDED,
    SYNC_OK,
    SYNC_SKIPPED,
    Plan,
    PlanSyncRun,
    PlanSyncWarning,
)
from app.db.models.teitori import BoardTeitori
from app.db.models.records import (
    ApiRequest,
    LineEvent,
    LineOperator,
    RunCompletion,
    RunCorrection,
    RunEvent,
    RunInput,
    RunNgInput,
)

__all__ = [
    "ActualsExport",
    "SideLink",
    "AdminCredential",
    "AllowedNetwork",
    "AdminLoginAttempt",
    "AdminSession",
    "AuditLog",
    "BoardTeitori",
    "PLAN_ACTIVE",
    "PLAN_CANCELLED",
    "SYNC_ERROR",
    "SYNC_GUARDED",
    "SYNC_OK",
    "SYNC_SKIPPED",
    "ApiRequest",
    "Equipment",
    "Line",
    "LineEvent",
    "LineOperator",
    "Operator",
    "Plan",
    "PlanSyncRun",
    "PlanSyncWarning",
    "Reason",
    "RunCompletion",
    "RunCorrection",
    "RunEvent",
    "RunInput",
    "RunNgInput",
]
