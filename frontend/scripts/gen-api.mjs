// APIの型を FastAPI の OpenAPI から自動生成する(npm run gen:api)。
// バックエンドの venv の Python で OpenAPI を書き出し、openapi-typescript で src/api/schema.ts を作る。
// Python の場所は環境変数 GENBA_PYTHON で変えられる(既定は ../backend/.venv の Python)。
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = resolve(frontend, "../backend");
const python =
  process.env.GENBA_PYTHON ??
  (process.platform === "win32" ? join(backend, ".venv", "Scripts", "python.exe") : join(backend, ".venv", "bin", "python"));

const work = mkdtempSync(join(tmpdir(), "genba-openapi-"));
try {
  const jsonPath = join(work, "openapi.json");
  execFileSync(python, ["-m", "app.openapi_export", jsonPath], { cwd: backend, stdio: "inherit" });
  const schema = JSON.parse(readFileSync(jsonPath, "utf-8"));
  const body = astToString(await openapiTS(schema));
  const header =
    "// このファイルは自動生成です。手で編集しないこと(npm run gen:api で作り直す)。\n" +
    "// 元: バックエンドの OpenAPI(app.openapi_export)、生成: openapi-typescript\n\n";
  writeFileSync(join(frontend, "src", "api", "schema.ts"), header + body, "utf-8");
  console.log("src/api/schema.ts を生成しました");
} finally {
  rmSync(work, { recursive: true, force: true });
}
