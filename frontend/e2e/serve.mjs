// 画面の確認用のバックエンドを起動する(playwright.config.ts の webServer から呼ぶ)。
// test-results/e2e-data/ に確認用のDBを作り直し、決まった稼働日の確認用のデータを入れてから、ビルドした画面ごと配信する。
// 撮る時刻によって画面が変わらないよう、サーバーの時計は GENBA_CLOCK_START(確認用の稼働日の 10:00)から進める。
// 既存アプリのDBは設定しない(legacy_app_dir なし)。
import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const E2E_DATE = "2026-10-21"; // e2e/screens.spec.ts の日付と合わせる
const CLOCK_START = `${E2E_DATE}T10:00:00+09:00`;
const E2E_ADMIN_PASSWORD = "e2e-admin-pass"; // 確認用のDBだけで使う(毎回作り直す)

const port = process.argv[2] ?? "8765";
const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = resolve(frontend, "../backend");
const python =
  process.env.GENBA_PYTHON ??
  (process.platform === "win32" ? join(backend, ".venv", "Scripts", "python.exe") : join(backend, ".venv", "bin", "python"));

const dataDir = join(frontend, "test-results", "e2e-data");
rmSync(dataDir, { recursive: true, force: true });
mkdirSync(dataDir, { recursive: true });
const config = join(dataDir, "config.toml");
writeFileSync(config, `[paths]\ndatabase = "${join(dataDir, "genba.db").replaceAll("\\", "/")}"\n`, "utf-8");

// テスト用の時計は GENBA_TEST_MODE=1 と組でだけ有効になる(app/core/clock.py)
const env = {
  ...process.env, GENBA_CONFIG: config, GENBA_STATIC_DIR: join(frontend, "dist"),
  GENBA_CLOCK_START: CLOCK_START, GENBA_TEST_MODE: "1",
};
execFileSync(python, ["-m", "app.cli", "demo-seed", "--line", "S", "--date", E2E_DATE], { cwd: backend, env, stdio: "inherit" });
// 管理画面の確認用: demo-seed が入れた管理者 A001 のパスワード(e2e/admin.spec.ts と合わせる)
execFileSync(python, ["-m", "app.cli", "admin", "set-password", "--worker-id", "A001", "--stdin"], {
  cwd: backend, env, input: `${E2E_ADMIN_PASSWORD}
`, stdio: ["pipe", "inherit", "inherit"],
});

const server = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port], {
  cwd: backend, env, stdio: "inherit",
});
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
process.on("exit", stop);
server.on("exit", (code) => process.exit(code ?? 0));
