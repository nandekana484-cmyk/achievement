# PyInstaller の設定(packaging/build.ps1 から使う)。フォルダ形式(onedir)で packaging/dist/v<版>/ にまとめる。
# 同梱するもの: 画面のビルド結果(frontend/dist)、マイグレーション、時刻帯のデータ(tzdata)。詳細: docs/design/packaging.md
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821  SPECPATH は PyInstaller が渡す
BACKEND = ROOT / "backend"
VERSION = re.search(r'__version__ = "([^"]+)"', (BACKEND / "app" / "__init__.py").read_text(encoding="utf-8")).group(1)

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
    console=True,  # コンソールを出す形(ログを画面でも確かめられる)。ログは logs\genba.log にも出る
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=f"v{VERSION}", upx=False)  # noqa: F821
