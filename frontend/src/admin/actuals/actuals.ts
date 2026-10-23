// 実績の書き出しの画面の計算: 直した数、キッティングNo.ごとの合計の確かめ、送る数。サーバーも同じ確かめをする。
// 詳細: docs/design/actuals-export.md
import type { components } from "../../api/schema";

export type ActualsRow = components["schemas"]["ActualsRowOut"];
export type Edits = Record<string, number>; // rowKey → 直した生産数

export const rowKey = (r: Pick<ActualsRow, "kitting_no" | "lot_no">) => `${r.kitting_no}\u0000${r.lot_no}`;

export const qtyOf = (r: ActualsRow, edits: Edits) => edits[rowKey(r)] ?? r.produced_qty;

export type Mismatch = { kitting_no: string; sum: number; total: number };

/** ロットの合計(一覧に出さない面2にまとめたロットの分も含む)が、キッティングNo.の累計と合わないもの。 */
export function mismatches(rows: ActualsRow[], edits: Edits): Mismatch[] {
  const sums = new Map<string, Mismatch>();
  for (const r of rows) {
    const m = sums.get(r.kitting_no) ?? { kitting_no: r.kitting_no, sum: r.kitting_hidden_qty, total: r.kitting_produced_total };
    m.sum += qtyOf(r, edits);
    sums.set(r.kitting_no, m);
  }
  return [...sums.values()].filter((m) => m.sum !== m.total);
}

/** サーバーに送る、直した行の数(割り振りのままの行は送らない)。 */
export function quantitiesToSend(rows: ActualsRow[], edits: Edits) {
  return rows
    .filter((r) => qtyOf(r, edits) !== r.produced_qty)
    .map((r) => ({ kitting_no: r.kitting_no, lot_no: r.lot_no, produced_qty: qtyOf(r, edits) }));
}

/** 入力欄の文字を数にする(0以上の整数でなければ null)。 */
export function parseQty(text: string): number | null {
  return /^\d+$/.test(text.trim()) ? Number(text.trim()) : null;
}
