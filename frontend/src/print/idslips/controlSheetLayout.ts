// K社製品ロット管理票の組み立て(React に依存しない): 印刷する工程の行、当ロット数 A / C、1ページに収める詰め具合。
// 欄と元データ: docs/design/control-sheet.md
import type { components } from "../../api/schema";
import type { IdSlip } from "./idSlipLogic";

export type ControlRow = components["schemas"]["ControlRow"];
export type Kind = ControlRow["kind"];

export type SheetRow = { no: number; name: string; nameVi: string; kind: Kind; procedure: string; useLine: boolean };

/** 印刷する工程の行(番号は1から)。サーバーが、登録した行に、8行になるまでの空の行(ライン名の欄に斜線)を足して返す。未登録のときは空の8行。 */
export function sheetRows(cs: IdSlip["control_sheet"]): SheetRow[] {
  return cs.rows.map((r, i) => ({ no: i + 1, name: r.name, nameVi: r.name_vi ?? "", kind: r.kind, procedure: r.procedure, useLine: r.use_line }));
}

/** 当ロット数「A / C」。A = この計画での生産数、C = 発注数(無ければ空)。 */
export function lotCounts(slip: IdSlip, lotNo: string): { a: string; c: string } {
  const lot = slip.lots.find((l) => l.lot_no === lotNo);
  return { a: lot ? String(lot.planned_qty) : "", c: lot?.order_qty != null ? String(lot.order_qty) : "" };
}

/** 詰め具合の段階数(controlsheet.css の .sk-d0 〜 .sk-d7)。0 が様式のまま。段階が上がるほど、先に行の高さ(1〜3)、あとで文字(4〜6。最小 8px)、最後に上の欄と下の欄の余白(7)を縮める。 */
export const LEVEL_COUNT = 8;

/** 用紙(297mm - 上下の余白 16mm = 281mm ≒ 1062px)に収まる高さの上限(px)。余裕を少し見る。 */
export const MAX_HEIGHT_PX = 1056;

/** 一番詰めても収まらないか(最後の段階で、まだ高さが上限を超える)。 */
export function overflowsAtLimit(level: number, heightPx: number): boolean {
  return level >= LEVEL_COUNT - 1 && heightPx > MAX_HEIGHT_PX;
}

/** 収まらないときの次の段階(収まる、またはこれ以上詰められなければ null)。 */
export function nextLevel(level: number, heightPx: number): number | null {
  return heightPx > MAX_HEIGHT_PX && level < LEVEL_COUNT - 1 ? level + 1 : null;
}
