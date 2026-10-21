// 画面の文言の漏れの確認: 画面のファイルに日本語の文字が直接書かれていないこと(文言は ja.ts に集める)。
// コメント、テストのファイル、辞書(ja.ts・vi.ts)、自動生成のAPIの型(src/api/)は除く。
// (node の API を使うので、型の検査(tsc)の対象の src ではなく scripts に置く)
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const SKIP = new Set(["i18n/ja.ts", "i18n/vi.ts", "i18n/translate.ts"]); // translate.ts は言語の名前(「日本語」)を持つ

// ひらがな・カタカナ・漢字と、全角の記号(「、」「〜」「(」など)
const JAPANESE = /[　-〿぀-ヿ㐀-鿿＀-￯]/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const path = join(dir, e.name);
    if (e.isDirectory()) return e.name === "api" ? [] : sourceFiles(path);
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [path] : [];
  });
}

/** コメントを除く(// の行末までと /* … *\/。JSX の {/* … *\/} も)。文字列の中の // は URL などで使わない前提。 */
function stripComments(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

describe("画面の文言の漏れ", () => {
  const files = sourceFiles(SRC).map((p) => relative(SRC, p).replaceAll("\\", "/")).filter((p) => !SKIP.has(p));

  it("確かめる対象がある(.tsx と、画面から切り離した .ts)", () => {
    expect(files.some((f) => f.endsWith(".tsx"))).toBe(true);
    expect(files).toContain("field/line/steps.ts");
  });

  it.each(files)("%s に日本語の文字が直接書かれていない", (file) => {
    const lines = stripComments(readFileSync(join(SRC, file), "utf-8")).split("\n");
    const found = lines.map((line, i) => ({ line: i + 1, text: line.trim() })).filter((l) => JAPANESE.test(l.text));
    expect(found).toEqual([]);
  });
});
