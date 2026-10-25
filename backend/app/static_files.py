"""画面(frontend/dist)の配信。配信フォルダの外のファイルは、どんな書き方でも返さない(404)。

画面の遷移用に、存在しないパスは index.html を返す。/api/ で始まる未知のパスは JSON の 404。
詳細: docs/design/security.md(S-01、S-15)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _unsafe(path: str) -> bool:
    """パスの書き方そのものが危ないか。デコードは1回済み(二重エンコードは % が残るので、ここで拒否する)。"""
    if not path:
        return False
    if path.startswith("/") or any(c in path for c in ("\\", "\0", "%", ":")):
        return True  # 絶対パス、バックスラッシュ、NULL、二重エンコード、ドライブ文字
    # Windows は名前の末尾の「.」と空白を無視するので、「.. 」や「...」も親のフォルダとして働く
    return any(seg.strip(" .") == "" and seg != "" for seg in path.split("/"))


def resolve_static_file(static_dir: Path, path: str) -> Path | None:
    """配信フォルダの中にある実在のファイルだけを返す。無ければ None。危ない書き方は HTTPException(404)。"""
    if _unsafe(path):
        raise HTTPException(status_code=404)
    if not path:
        return None
    root = static_dir.resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=404)
    return candidate if candidate.is_file() else None


def mount_spa(app: FastAPI, static_dir: Path, closed_paths: tuple[str, ...] = ()) -> None:
    """/assets と、画面の受け皿(上のとおり)を登録する。API のルートより後に呼ぶ。

    closed_paths: 画面の受け皿に渡さず 404 にするパス(閉じた /docs など。index.html の 200 を返さないため)。
    """
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path in closed_paths:
            raise HTTPException(status_code=404)
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="APIが見つかりません")
        found = resolve_static_file(static_dir, path)
        return FileResponse(found or static_dir / "index.html")
