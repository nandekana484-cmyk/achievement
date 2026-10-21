"""OpenAPI の定義を JSON で書き出す(画面のAPIクライアントの自動生成に使う。npm run gen:api から呼ぶ)。

使い方(backend フォルダで、venv の中で): python -m app.openapi_export <出力先のファイル>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("使い方: python -m app.openapi_export <出力先のファイル>", file=sys.stderr)
        return 2
    out = Path(args[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
