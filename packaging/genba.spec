# PyInstaller の設定(packaging/build.ps1 から使う)。フォルダ形式(onedir)で packaging/dist/v<版>/ にまとめる。
# 同梱するもの: 画面のビルド結果(frontend/dist)、マイグレーション、時刻帯のデータ(tzdata)。詳細: docs/design/packaging.md
import os
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821  SPECPATH は PyInstaller が渡す
BACKEND = ROOT / "backend"
VERSION = re.search(r'__version__ = "([^"]+)"', (BACKEND / "app" / "__init__.py").read_text(encoding="utf-8")).group(1)
# 標準はウィンドウを出さない形。build.ps1 -Console(GENBA_CONSOLE=1)のときだけ、コンソールを出す形(困ったときの確認用)
CONSOLE = os.environ.get("GENBA_CONSOLE") == "1"

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend_dist"),  # app/main.py の STATIC_DIR
    (str(BACKEND / "app" / "db" / "migrations"), "app/db/migrations"),  # alembic はファイルとして読む(app/db/migrate.py)
    *collect_data_files("tzdata"),  # Windows には時刻帯のデータが無い
]
hiddenimports = [
    *collect_submodules("app"),
    *collect_submodules("uvicorn"),
    *collect_submodules("alembic", filter=lambda name: not name.startswith("alembic.testing")),
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "_pytest", "httpx"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GenbaApp",
    console=CONSOLE,  # どちらの形でも、ログは <基準>\logs\genba.log に出る
    upx=False,
)
# 開発用コマンド(GenbaCli.exe)。管理者のパスワードの設定など、入力が要るのでいつもコンソールを出す
cli = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "cli_entry.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "_pytest", "httpx"],
)
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, name="GenbaCli", console=True, upx=False)  # noqa: F821
coll = COLLECT(  # noqa: F821
    exe, a.binaries, a.datas, cli_exe, cli.binaries, cli.datas,
    name=f"v{VERSION}-console" if CONSOLE else f"v{VERSION}", upx=False,
)
