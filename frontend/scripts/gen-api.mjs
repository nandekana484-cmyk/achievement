// APIの型を FastAPI の OpenAPI から自動生成する(npm run gen:api)。
// バックエンドの venv の Python で OpenAPI を書き出し、openapi-typescript で src/api/schema.ts を作る。
// --check を付けると、書き込まずに今の schema.ts と比べ、違えば終了コード 1(バックエンドとの食い違いの検出)。
// Python の場所は環境変数 GENBA_PYTHON で変えられる(既定は ../backend/.venv の Python)。
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = resolve(frontend, "../backend");
const target = join(frontend, "src", "api", "schema.ts");
const python =
  process.env.GENBA_PYTHON ??
  (process.platform === "win32" ? join(backend, ".venv", "Scripts", "python.exe") : join(backend, ".venv", "bin", "python"));
const HEADER =
  "// このファイルは自動生成です。手で編集しないこと(npm run gen:api で作り直す)。\n" +
  "// 元: バックエンドの OpenAPI(app.openapi_export)、生成: openapi-typescript\n\n";

async function generate() {
  const work = mkdtempSync(join(tmpdir(), "genba-openapi-"));
  try {
    const jsonPath = join(work, "openapi.json");
    execFileSync(python, ["-m", "app.openapi_export", jsonPath], { cwd: backend, stdio: ["ignore", "ignore", "inherit"] });
    const schema = JSON.parse(readFileSync(jsonPath, "utf-8"));
    return HEADER + astToString(await openapiTS(schema));
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}

const generated = await generate();
if (process.argv.includes("--check")) {
  const current = existsSync(target) ? readFileSync(target, "utf-8").replaceAll("\r\n", "\n") : "";
  if (current !== generated) {
    console.error("src/api/schema.ts がバックエンドの API と食い違っています。npm run gen:api で作り直してください");
    process.exit(1);
  }
  console.log("src/api/schema.ts はバックエンドの API と一致しています");
} else {
  writeFileSync(target, generated, "utf-8");
  console.log("src/api/schema.ts を生成しました");
}
