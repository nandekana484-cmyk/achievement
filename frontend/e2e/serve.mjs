// 画面の確認用のバックエンドを起動する(playwright.config.ts の webServer から呼ぶ)。
// test-results/e2e-data/ に確認用のDBを作り直し、今日の確認用のデータを入れてから、ビルドした画面ごと配信する。
// 既存アプリのDBは設定しない(legacy_app_dir なし)。
import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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

const env = { ...process.env, GENBA_CONFIG: config, GENBA_STATIC_DIR: join(frontend, "dist") };
const today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10); // 日本時間の今日
execFileSync(python, ["-m", "app.cli", "demo-seed", "--line", "S", "--date", today], { cwd: backend, env, stdio: "inherit" });

const server = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port], {
  cwd: backend, env, stdio: "inherit",
});
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
process.on("exit", stop);
server.on("exit", (code) => process.exit(code ?? 0));
