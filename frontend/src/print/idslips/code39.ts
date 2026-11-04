// 識別票のバーコード(Code 39)。JsBarcode(MIT。npm で入れてアプリに含める)で符号にし、SVG はこちらで mm の大きさで描く。
// 細いバーの幅は印刷で 0.25mm 以上にする。詳細: docs/design/id-slips.md
import JsBarcode from "jsbarcode";

/** 細いバーの最小幅(mm。印刷の大きさ)。 */
export const MIN_BAR_MM = 0.25;

const CODE39 = /^[0-9A-Z\-. $/+%]+$/;

/** Code 39 で表せる値か(英大文字・数字・記号 - . 空白 $ / + % だけ。英小文字や日本語は表せない。大文字には直さない)。 */
export function isCode39(value: string): boolean {
  return CODE39.test(value);
}

/** Code 39 の符号(1 = 黒、0 = 白。先頭と末尾の * を含み、末尾の白は除く)。表せない値は null。 */
export function encodeCode39(value: string): string | null {
  if (!isCode39(value)) return null;
  const target: { encodings?: { data: string }[] } = {};
  JsBarcode(target, value, { format: "CODE39" });
  return target.encodings?.[0]?.data.replace(/0+$/, "") ?? null;
}

/** 符号の長さ(細いバー何本分か)。1文字 = 16(太いバー 3、細いバー 6 で 15 + 文字の間の 1)、先頭と末尾の * を含む。 */
export function modulesOf(value: string): number {
  return (value.length + 2) * 16 - 1;
}

export type BarSize = { barMm: number; widthMm: number; fits: boolean };

/** 枠(availableMm)に収まる範囲で、細いバーを MIN_BAR_MM 以上 maxMm 以下にする。0.25mm でも収まらないときは 0.25mm にして fits = false。 */
export function barSize(value: string, availableMm: number, maxMm = 0.4): BarSize {
  const modules = modulesOf(value);
  const fit = Math.floor((availableMm / modules) * 100) / 100;
  const barMm = Math.max(MIN_BAR_MM, Math.min(maxMm, fit));
  return { barMm, widthMm: modules * barMm, fits: modules * barMm <= availableMm + 1e-9 };
}

/** 1 の連なりを SVG の path にする(viewBox は横 = 符号の長さ、縦 = 1)。 */
export function barsPath(data: string): string {
  let d = "";
  for (const m of data.matchAll(/1+/g)) d += `M${m.index} 0h${m[0].length}v1h-${m[0].length}z`;
  return d;
}
