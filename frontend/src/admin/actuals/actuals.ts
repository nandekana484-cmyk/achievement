// 実績の書き出しの画面の計算: 直した数、キッティングNo.ごとの合計の確かめ、送る数。サーバーも同じ確かめをする。
// 詳細: docs/design/actuals-export.md
import type { components } from "../../api/schema";

export type ActualsRow = components["schemas"]["ActualsRowOut"];
export type LinkCheck = components["schemas"]["LinkCheckOut"];
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

/** ひも付けの確認で「つながない」を表す選択の値。 */
export const NO_LINK = "__no_link__";

export const linkKey = (c: Pick<LinkCheck, "side1_kitting_no" | "lot_no">) => `${c.side1_kitting_no}\u0000${c.lot_no}`;

/** 初期の選択: 確定したものはその結果、未確定なら発行日が最も近い面2(サーバーが決める)。選べる面2が無ければ空。 */
export function initialChoice(c: Pick<LinkCheck, "state" | "side2_kitting_no" | "suggested">): string {
  if (c.state === "confirmed" && c.side2_kitting_no) return c.side2_kitting_no;
  if (c.state === "unlinked") return NO_LINK;
  return c.suggested ?? "";
}
