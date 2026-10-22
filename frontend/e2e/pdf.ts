// PDF の中身を調べる補助(印刷の確認用)。
import { inflateSync } from "node:zlib";

/** PDF の中の描画の命令(圧縮を展開したもの)。 */
export function pdfContent(pdf: Buffer): string {
  const text = pdf.toString("latin1");
  const out: string[] = [];
  for (const m of text.matchAll(/stream\r?\n/g)) {
    const start = (m.index ?? 0) + m[0].length;
    const end = text.indexOf("endstream", start);
    try {
      out.push(inflateSync(pdf.subarray(start, end)).toString("latin1"));
    } catch {
      /* 圧縮されていない(画像やフォントなど)ものは読まない */
    }
  }
  return out.join("\n");
}

/** PDF のページ数。 */
export function pdfPageCount(pdf: Buffer): number {
  return (pdf.toString("latin1").match(/\/Type\s*\/Page\b(?!s)/g) ?? []).length;
}
