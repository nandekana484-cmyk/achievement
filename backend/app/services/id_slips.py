"""識別票(4種類)に印刷する値を組み立てる。DBは読むだけ(記録は変えない)。

欄と元データ: docs/design/id-slips.md
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import PLAN_CANCELLED
from app.domain.id_slip import display_file_no, lot_list, suf_value
from app.services.control_sheets import ControlSheetPrintOut, print_data
from app.services.errors import RuleViolation
from app.services.kitting_plans import load_group


class IdSlipLotOut(BaseModel):
    lot_no: str
    order_qty: int | None  # C: ロットの全発注数(LOT総数)。無ければ空
    planned_qty: int  # A: この計画での生産数(plans.planned_qty。管理表の「当ロット数」)


class IdSlipOut(BaseModel):
    kitting_no: str
    line_code: str
    run_no: int  # 1=1回目(面1)、2=2回目(面2)
    file_no: str  # 表示用(先頭の0を外したもの)
    suf: str  # 下のバーコードの値(SUF- + 保存されている4桁のファイルNo.)
    product_name: str
    lots: list[IdSlipLotOut]  # このキッティングNo.の全ロット(ロットNo.の順)
    lot_list: str  # 4つ目の「Lot」の欄(「, 」区切り)
    control_sheet: ControlSheetPrintOut  # 5つ目(管理表)に印刷する、ファイルNo.ごとの内容(未登録なら registered=False)


def build_id_slips(session: Session, kitting_no: str) -> IdSlipOut:
    """キッティングNo.の識別票の値。取り消しの印がある計画は出さない(409)。"""
    group = load_group(session, kitting_no)
    if group.status == PLAN_CANCELLED:
        raise RuleViolation("取り消された計画の識別票は印刷できません")
    lots = [IdSlipLotOut(lot_no=p.lot_no, order_qty=p.order_qty, planned_qty=p.planned_qty) for p in group.lots]
    return IdSlipOut(
        kitting_no=kitting_no, line_code=group.line_code, run_no=group.run_no, file_no=display_file_no(group.file_no),
        suf=suf_value(group.file_no), product_name=group.product_name, lots=lots, lot_list=lot_list([x.lot_no for x in lots]), control_sheet=print_data(session, group.file_no),
    )
