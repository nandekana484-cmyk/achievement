// ロットへの割り振りの画面(印刷のページの操作バー)の、React に依存しない部分。詳細: docs/design/actuals-export.md
import type { components } from "../api/schema";

export type Allocation = components["schemas"]["AllocationOut"];

/** 入力欄の文字を数に直す(空、負、小数は null)。 */
export function parseQty(text: string): number | null {
  const s = text.trim();
  return /^\d+$/.test(s) ? Number(s) : null;
}

/** 入力の合計(読めない欄があれば null)。 */
export function sumOf(drafts: string[]): number | null {
  const qs = drafts.map(parseQty);
  return qs.some((q) => q === null) ? null : (qs as number[]).reduce((a, b) => a + b, 0);
}

/** 保存できるか: 作業者IDが入っていて、全部の欄が数で、合計が生産数の合計と一致する。 */
export function canSaveAllocation(drafts: string[], total: number, workerId: string): boolean {
  return workerId.trim() !== "" && sumOf(drafts) === total;
}

/** 数を {ロットNo.: 数} にする。 */
export function toQuantities(lots: { lot_no: string }[], drafts: string[]): Record<string, number> {
  return Object.fromEntries(lots.map((l, i) => [l.lot_no, parseQty(drafts[i]) ?? 0]));
}

/** 割り振りの画面を出すか(サーバーが決める)。 */
export function showAllocation(a: Allocation | null | undefined): a is Allocation {
  return Boolean(a?.editable);
}
