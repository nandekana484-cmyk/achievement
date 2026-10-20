# 現場実績入力・稼働率可視化Webアプリ

仕様は [docs/spec.md](docs/spec.md) を参照。

## 開発環境の準備(Windows、開発者PC)

必要なもの:

- Python 3.14(`.python-version`)。`py -3.14` で起動できること
- Node.js 22(`frontend/.nvmrc`)
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

## 本番と同じ形で確認する

```powershell
cd frontend
npm run build
cd ..\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

http://localhost:8000 で画面とAPIが1つのプロセスから配信される。

## 2拠点での作業

作業の前に main を `git pull` し、`feature/<内容>` のブランチで作業する。詳しいルールは [AGENTS.md](AGENTS.md) の「2拠点での作業ルール」を参照。
