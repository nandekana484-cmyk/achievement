# AIアシスタント向けの指示

このリポジトリは「現場実績入力・稼働率可視化Webアプリ」です。

- **作業を始める前に、必ず `docs/spec.md`(開発指針)を読むこと。** 仕様の唯一の基準です
- 特に `docs/spec.md` の「0. AIアシスタントへの指示」は必ず守ること
- 「11. 未確定事項」にある内容は勝手に決めず、仮置きで実装するときは `TODO(要確認): <項目名>` をコードに残すこと
- 既存の生産管理アプリのDBには絶対に書き込まないこと

## 構成

- `backend/` Python + FastAPI + SQLAlchemy(SQLite)。`app/` の層は api / services / db / integration / core / domain
- `frontend/` React + TypeScript + Vite。`src/field`(現場画面)、`src/admin`(管理画面)、`src/print`(記録用紙)
- 本番は、ビルドした `frontend/dist` をFastAPIが配信する1プロセス構成

## コマンド

Python は 3.14(`.python-version`)、Node.js は 22(`frontend/.nvmrc`)。
PATH の `python` は既存アプリ用の 3.10 の可能性があるため、**Python のコマンドはすべて venv の中で実行する**。

- venv の作成(初回のみ): `cd backend` → `py -3.14 -m venv .venv` → `.\.venv\Scripts\Activate.ps1` → `pip install -r requirements-dev.txt`
- venv の有効化: `cd backend` → `.\.venv\Scripts\Activate.ps1`(以降は `python ...` でよい)
- バックエンドのテスト: `cd backend` → `python -m pytest`
  (有効化していない場合は `.\.venv\Scripts\python.exe -m pytest`)
- バックエンドの起動: `cd backend` → `python -m uvicorn app.main:app --reload --port 8000`
  (有効化していない場合は `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000`)
- マスタの追加と一覧(開発用): `cd backend` → `python -m app.cli operators add <名前>` / `operators list` / `equipment add <ライン> <名前>` / `equipment list` / `reasons list` / `lines list`(対象は config.toml の `paths.database`)
- DBの構造の変更: モデル(`app/db/models.py`)を変えたら、マイグレーションを `app/db/migrations/versions/` に追加する。起動時に自動で最新に更新される(`tests/test_db.py` がモデルとマイグレーションの食い違いを検出する)
  - **Alembic を手で使う**(`python -m alembic ...`)**ときの対象は、config.toml(`GENBA_CONFIG`)の `paths.database`**。本番のDBを指していないか確認してから実行する
- フロントエンドの依存の導入: `cd frontend` → `npm ci`(`package-lock.json` のとおりに入れる)
- フロントエンドの開発: `cd frontend` → `npm run dev`(`/api` は8000番へ転送)
- フロントエンドのビルド: `cd frontend` → `npm run build`

## 2拠点での作業ルール

開発は2拠点の別々のPCで行う。GitHub のリポジトリ(`origin`)を介して同期する。

- **作業の前に、必ず main を `git pull` する**(`git switch main` → `git pull`)
- 作業は `feature/<内容>` のブランチで行い、完了したら push する。**main への取り込みはレビュー後**に行う(main へ直接コミットしない)
- **既存アプリのDB、本番データ、`config.toml` は絶対にコミットしない。**
  テスト用の既存DBの複製は、各PCの `legacy-db/`(Git の対象外)に置く
- 依存ライブラリを追加・変更したら、`backend/requirements.txt`(`requirements-dev.txt`)/ `frontend/package-lock.json` を必ずコミットする
- pull して依存が変わっていたら、`pip install -r requirements-dev.txt`(venv の中で)と `npm ci` をやり直す

## 書き方の約束

- 現在時刻は `app.core.clock.now()` を使う(`datetime.now()` を直接使わない)
- PCに依存する値は `app.core.config` から読む(パスやポートを直書きしない)
- 業務ルールは `services/` と `domain/` に置き、`api/` には書かない
- 新しいロジックにはテストを付ける
- 画面の文言は日本語。用語は `docs/spec.md` の「2. 用語集」に従う
