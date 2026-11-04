// 枠に収まる文字の大きさを決める(最小 minPx まで縮める)。描いたあとの測定はせず、文字の幅の見積りで決める(印刷の結果が毎回同じになるように)。
// 見積りは余裕を持たせてある(太字の半角の大文字・数字・記号 0.72em、小文字 0.62em、空白 0.3em、全角 1.05em、行の高さ 1.2)。収まらなければ minPx。

const PX_PER_MM = 96 / 25.4;
export const mmToPx = (mm: number) => mm * PX_PER_MM;

/** 文字列の幅(em)。 */
export function textEm(text: string): number {
  let em = 0;
  for (const ch of text) em += ch === " " ? 0.3 : /[a-z]/.test(ch) ? 0.62 : /[!-~]/.test(ch) ? 0.72 : 1.05;
  return em;
}

type Box = { widthPx: number; heightPx: number; maxPx: number; minPx?: number; maxLines?: number };

/** 区切りの「, 」の幅(em)。 */
const SEPARATOR_EM = 0.3 + textEm(",");

/** 項目(ロットNo. など)を「, 」で並べ、項目の途中では折り返さないときの行数。 */
export function listLines(items: string[], px: number, widthPx: number): number {
  let lines = 1;
  let used = 0;
  for (const item of items) {
    const w = (textEm(item) + SEPARATOR_EM) * px;
    if (used > 0 && used + w > widthPx) { lines += 1; used = 0; }
    used += w;
  }
  return lines;
}

/** 項目を並べたものが枠に収まる最大の文字の大きさ(px)。1項目が枠より広いときは、その項目の途中で折り返すので、行数はその分多く数える。 */
export function fitListFontPx(items: string[], { widthPx, heightPx, maxPx, minPx = 8 }: Box): number {
  for (let px = Math.floor(maxPx); px > minPx; px--) {
    const wide = items.reduce((n, item) => n + Math.max(0, Math.ceil((textEm(item) * px) / widthPx) - 1), 0);
    if ((listLines(items, px, widthPx) + wide) * px * 1.2 <= heightPx) return px;
  }
  return minPx;
}

/** 枠(widthPx × heightPx)に収まる最大の文字の大きさ(px。整数)。折り返しは文字の途中でもよい(CSS の word-break: break-all)前提。 */
export function fitFontPx(text: string, { widthPx, heightPx, maxPx, minPx = 8, maxLines = Infinity }: Box): number {
  const em = textEm(text);
  for (let px = Math.floor(maxPx); px > minPx; px--) {
    const lines = Math.max(1, Math.ceil((em * px) / widthPx));
    if (lines <= maxLines && lines * px * 1.2 <= heightPx) return px;
  }
  return minPx;
}
