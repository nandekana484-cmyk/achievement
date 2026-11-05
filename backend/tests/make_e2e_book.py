"""Playwright(frontend/e2e/zz-control-sheet-import.spec.ts)が管理画面から取り込む、テスト用のブックを作る。ユーザーの Excel ではなく、コードで作ったもの。

使い方: cd backend → python tests/make_e2e_book.py <出力の .xlsx>。frontend/e2e/serve.mjs が呼ぶ。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from book_helpers import Cluster, SheetSpec, build_xlsx, example_sheet  # noqa: E402


def main(out: str) -> None:
    new = SheetSpec(name="930", manager_no="MP-0930", file_no_cell="0930", clusters=[
        Cluster(1, ["リフロー", "社内", "INTERNO"], ["Side A", "温度 245℃"]),
        Cluster(2, ["外観検査", "社外", "EXTERNO"], ["全数", "", "不良はNGへ"], diagonal="up"),
        Cluster(3, [], [], rows=2),
    ])
    changed = example_sheet("0940", manager_no="MP-0940N", file_no_cell="")
    error = example_sheet("0960", skip={"manager"})  # 見出しが無いのでエラー
    Path(out).write_bytes(build_xlsx(new, changed, example_sheet("Sheet1"), error))


if __name__ == "__main__":
    main(sys.argv[1])
