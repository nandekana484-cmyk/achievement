// 自動生成したAPIの型(src/api/schema.ts)が、バックエンドの OpenAPI と食い違っていないか。
// バックエンドの venv が必要(README の「開発環境の準備」)。食い違っていたら npm run gen:api で作り直す。
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const script = join(dirname(fileURLToPath(import.meta.url)), "gen-api.mjs");

it("src/api/schema.ts はバックエンドの API と一致している", () => {
  const r = spawnSync(process.execPath, [script, "--check"], { encoding: "utf-8" });
  expect(r.stderr + r.stdout).toContain("一致しています");
  expect(r.status).toBe(0);
}, 60_000);
