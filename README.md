# 現場実績入力・稼働率可視化Webアプリ

作業の再開は [docs/STATUS.md](docs/STATUS.md) から。

仕様は [docs/spec.md](docs/spec.md) を参照。

## 開発環境の準備(Windows、開発者PC)

必要なもの:

- Python 3.14(`.python-version`)。`py -3.14` で起動できること
- Node.js 22.12 以上(`frontend/.nvmrc`)
- Git

PATH の `python` は既存アプリが使う別の版(3.10 など)の可能性があるため、PATH は変えずに venv で 3.14 を使う。
Python のコマンドは、すべて venv を有効化してから実行する。

```powershell
cd C:\work\achievement

# バックエンド
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
# 有効化を忘れた場合でも動く形: .\.venv\Scripts\python.exe -m pytest
cd ..

# フロントエンド(package-lock.json のとおりに入れる)
cd frontend
npm ci
cd ..

# 設定ファイル
mkdir backend\data
copy config.example.toml backend\data\config.toml
```

## 起動(開発中)

ターミナルを2つ使う。

```powershell
# 1つ目: バックエンド
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8000
# 有効化を忘れた場合: .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 2つ目: フロントエンド
cd frontend
npm run dev
```

ブラウザで http://localhost:5173 を開く。稼働確認は http://localhost:8000/api/health 。

## 画面の確認用のデータ

既存アプリのDBを使わずに画面を確かめるときは、確認用の計画(14件・キッティングNo. 10件。1回目と2回目の組、時間の重なり、タクトなし、日付をまたぐ計画、次の稼働日の計画、表示範囲の終わりをまたぐ計画、3日前の未着手の計画、3ロットのキッティングNo.(面1と面2の組)を含む)と、作業者3名(作業者ID Y001・S002・Y015。同じ名前の人を含む)・設備2台を入れる。

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli demo-seed --line S --date 2026-10-21
```

- 対象は config.toml の `paths.database`。何度実行しても同じ結果になる
- config.toml に `paths.legacy_app_dir` が設定されているときは、実データと混ざらないよう、何もせずにエラーで止まる
- 日付は、ライン画面で見る稼働日(8:15〜翌8:15。ふつうは今の稼働日)にする

## 画面の開発(frontend)

```powershell
cd frontend
npm run gen:api   # APIの型を作り直す(バックエンドの OpenAPI → src/api/schema.ts)。APIを変えたら必ず実行する
npm test          # vitest(UUID、時刻と位置の変換、工程の状態、送り直し、言語の切り替え、画面の文言の漏れ)
npm run build
npx playwright install chromium   # 初回だけ(ブラウザをユーザーのフォルダに入れる)
npm run e2e       # Playwright。確認用のデータを入れたDBで画面を操作し、frontend/test-results/screens/ にスクリーンショットを撮る
```

`npm run e2e` は `npm run build` のあとで実行する(ビルドした画面をバックエンドが配信する形で確かめる)。確認用のDBは `frontend/test-results/e2e-data/` に毎回作り直す。

## DBの構造の更新(Alembic)

起動時に自動で最新の構造に更新される。手で `python -m alembic ...` を使うとき(backend フォルダで、venv の中で)は、**対象が config.toml(環境変数 `GENBA_CONFIG`、未指定なら `data\config.toml`)の `paths.database` になる**ので、どのDBを指しているか確認してから実行する。

## 本番と同じ形で確認する

```powershell
cd frontend
npm run build
cd ..\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

http://localhost:8000 で画面とAPIが1つのプロセスから配信される。

## 本番の版(exe)を作る

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1
```

画面のビルド → テスト → PyInstaller で `packaging\dist\v<版>\`(GenbaApp.exe)と `GenbaApp-v<版>.zip` を作る。担当者PCへの置き方、自動起動、ファイアウォール、バックアップは [docs/design/packaging.md](docs/design/packaging.md)。

## コードの大きさの確認

リポジトリ直下で `py -3.14 tools/check_code_size.py --top 10`(標準ライブラリだけで動く。ルールは [AGENTS.md](AGENTS.md) の「コードの大きさとコメントのルール」)。スクリプト自体のテストは `backend\.venv\Scripts\python.exe -m pytest tools/tests`。

## 2拠点での作業

作業の前に main を `git pull` し、`feature/<内容>` のブランチで作業する。詳しいルールは [AGENTS.md](AGENTS.md) の「2拠点での作業ルール」を参照。
