"""exe の入口(PyInstaller が最初に動かす)。中身は backend/app/server.py。"""

from app.server import main

if __name__ == "__main__":
    main()
