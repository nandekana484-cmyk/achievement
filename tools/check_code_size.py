"""コードの大きさとコメントの割合を調べる(AGENTS.md「コードの大きさとコメントのルール」)。

使い方(リポジトリ直下で): python tools/check_code_size.py [--top N]
目安に当たるファイルだけを一覧にする。アプリのコードで400行を超える「要分割」があれば終了コード 1。
標準ライブラリだけで動く(venv の外の Python でもよい)。
"""

from __future__ import annotations

import argparse
import ast
import io
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = ("backend/app", "backend/tests", "frontend/src")
EXTENSIONS = {".py", ".ts", ".tsx"}
# マイグレーションと自動生成のファイルは対象外
EXCLUDED_DIRS = ("backend/app/db/migrations", "frontend/src/api")
GENERATED_MARKERS = ("@generated", "auto-generated", "自動生成")

APP_WARN, APP_SPLIT, TEST_WARN = 300, 400, 500
COMMENT_RATIO_LIMIT = 0.25
RATIO_MIN_LINES = 20  # これより小さいファイルは、モジュールの説明だけで割合が大きくなるので割合を見ない
FUNCTION_LIMIT = 50


@dataclass
class FileStat:
    path: str
    is_test: bool
    lines: int  # ファイルの行数(空行も含む)
    code_lines: int  # 空行を除いた行数
    comment_lines: int  # コメントだけの行と docstring の行
    long_functions: list[tuple[str, int]] = field(default_factory=list)

    @property
    def comment_ratio(self) -> float:
        """コメントの割合 = コメントの行 ÷ 空行を除いた行。"""
        return self.comment_lines / self.code_lines if self.code_lines else 0.0

    def findings(self) -> list[str]:
        out: list[str] = []
        if self.is_test:
            if self.lines > TEST_WARN:
                out.append(f"テストが{TEST_WARN}行超(テーマごとに分ける)")
        elif self.lines > APP_SPLIT:
            out.append(f"要分割({APP_SPLIT}行超)")
        elif self.lines > APP_WARN:
            out.append(f"{APP_WARN}行超")
        if self.code_lines >= RATIO_MIN_LINES and self.comment_ratio > COMMENT_RATIO_LIMIT:
            out.append(f"コメント {self.comment_ratio:.0%}")
        for name, n in self.long_functions:
            out.append(f"関数 {name} が{n}行")
        return out

    @property
    def needs_split(self) -> bool:
        return not self.is_test and self.lines > APP_SPLIT


def _python_comment_lines(source: str) -> set[int]:
    """コメントだけの行と docstring の行の番号。"""
    lines: set[int] = set()
    code_lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            lines.add(tok.start[0])
        elif tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
            code_lines.update(range(tok.start[0], tok.end[0] + 1))
    lines -= code_lines  # 行末のコメントは数えない
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines.update(range(first.lineno, first.end_lineno + 1))
    return lines


def _python_long_functions(source: str) -> list[tuple[str, int]]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = node.end_lineno - node.lineno + 1
            if n > FUNCTION_LIMIT:
                found.append((node.name, n))
    return sorted(found, key=lambda x: -x[1])


def _ts_comment_lines(source: str) -> set[int]:
    """// の行と /* */ の中の行(文字列の中の // などは考えない簡易版)。"""
    lines: set[int] = set()
    in_block = False
    for no, raw in enumerate(source.splitlines(), start=1):
        s = raw.strip()
        if in_block:
            lines.add(no)
            in_block = "*/" not in s
        elif s.startswith("//"):
            lines.add(no)
        elif s.startswith(("/*", "{/*")):
            lines.add(no)
            in_block = "*/" not in s
    return lines


def analyze(path: Path) -> FileStat | None:
    rel = path.relative_to(ROOT).as_posix()
    source = path.read_text(encoding="utf-8")
    if any(m in "\n".join(source.splitlines()[:5]) for m in GENERATED_MARKERS):
        return None
    blank = {i for i, line in enumerate(source.splitlines(), start=1) if not line.strip()}
    total = len(source.splitlines())
    if path.suffix == ".py":
        comments = _python_comment_lines(source) - blank
        long_functions = _python_long_functions(source)
    else:
        comments = _ts_comment_lines(source) - blank
        long_functions = []
    is_test = rel.startswith("backend/tests/") or ".test." in path.name or ".spec." in path.name
    return FileStat(rel, is_test, total, total - len(blank), len(comments), long_functions)


def collect() -> list[FileStat]:
    stats = []
    for d in TARGET_DIRS:
        for path in sorted((ROOT / d).rglob("*")):
            rel = path.relative_to(ROOT).as_posix()
            if path.suffix not in EXTENSIONS or path.name.endswith(".d.ts") or not path.is_file():
                continue
            if any(rel.startswith(x + "/") for x in EXCLUDED_DIRS) or "__pycache__" in rel:
                continue
            stat = analyze(path)
            if stat is not None:
                stats.append(stat)
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="コードの大きさとコメントの割合を調べる")
    p.add_argument("--top", type=int, default=0, help="行数の多いファイルを上位 N 件表示する")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    stats = collect()
    flagged = [s for s in stats if s.findings()]
    print(f"対象 {len(stats)} ファイル / 目安に当たるファイル {len(flagged)} 件")
    for s in sorted(flagged, key=lambda x: -x.lines):
        kind = "テスト" if s.is_test else "アプリ"
        print(f"  {s.path}  {s.lines}行({kind})  コメント {s.comment_ratio:.0%}  : {' / '.join(s.findings())}")

    if args.top:
        print(f"行数の多いファイル 上位{args.top}件")
        for s in sorted(stats, key=lambda x: -x.lines)[: args.top]:
            print(f"  {s.lines:5d}行  コメント {s.comment_ratio:4.0%}  {s.path}")

    lines = sum(s.lines for s in stats)
    code = sum(s.code_lines for s in stats)
    comments = sum(s.comment_lines for s in stats)
    if code:
        print(f"全体: {lines}行(空行を除くと {code}行)、コメント {comments}行(空行を除いた行の {comments / code:.1%})")

    needs_split = [s.path for s in stats if s.needs_split]
    if needs_split:
        print(f"要分割: {len(needs_split)} 件")
        return 1
    print("要分割: なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
