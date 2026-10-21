"""開発用コマンドの exe(GenbaCli.exe)の入口。コンソールを出す形で、パスワードの入力(画面に出さない)ができる。

    GenbaCli.exe admin set-password --worker-id K0042

中身は backend/app/cli.py。基準のフォルダ(GENBA_HOME)の決め方は GenbaApp.exe と同じ。
"""

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
