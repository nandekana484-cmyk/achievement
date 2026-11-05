// 識別票の印刷の操作バーの決まり(React に依存しない): 種類の初期値、ロットの選択、ページの並び、Code 39 で表せない値の警告。
// 種類: 1 基板製品ロット現品票(ロットごと)、2 バーコード印字 完了(ロットごと)、3 1回目完了済み(ロットごと)、4 バーコード照合用(キッティングNo.ごと)、
// 5 K社製品ロット管理票(A4縦。ロットごと)。
import type { components } from "../../api/schema";
import { isCode39 } from "./code39";
import { SLIP_KINDS, type SlipKind } from "./idSlipTexts";

export type IdSlip = components["schemas"]["IdSlipOut"];

/** ロットごとの種類(1、2、3、5)。4 はキッティングNo.ごとに 1 枚(そのキッティングNo.の全ロットを並べる)。 */
export const isLotKind = (kind: SlipKind): boolean => kind !== 4;

export type Selection = { kinds: SlipKind[]; lots: string[] };

/** 初めにチェックが入る種類: 1回目(面1)の計画は 2・3・4、2回目(面2)の計画は 1・4・5(管理表)。 */
export function defaultKinds(runNo: number): SlipKind[] {
  return runNo === 2 ? [1, 4, 5] : [2, 3, 4];
}

export function initialSelection(slip: IdSlip): Selection {
  return { kinds: defaultKinds(slip.run_no), lots: slip.lots.map((l) => l.lot_no) };
}

/** 選んだ種類(SLIP_KINDS の順)。 */
export function toggleKind(kinds: SlipKind[], kind: SlipKind): SlipKind[] {
  return SLIP_KINDS.filter((k) => (k === kind ? !kinds.includes(k) : kinds.includes(k)));
}

/** 選んだロット(計画のロットの順)。 */
export function toggleLot(all: string[], selected: string[], lot: string): string[] {
  return all.filter((l) => (l === lot ? !selected.includes(l) : selected.includes(l)));
}

/**
 * 種類ごとのページ: ロットごとの種類は、選んだロットの数だけ(1ロット1ページ。同じロットの同じ種類を2ページ以上出さない)。
 * 4 は1ページ(lot は null)。枚数はブラウザの印刷の画面で決める。
 */
export function pagesOf(kind: SlipKind, sel: Selection): { lot: string | null }[] {
  return isLotKind(kind) ? [...new Set(sel.lots)].map((lot) => ({ lot })) : [{ lot: null }];
}

export type BarcodeWarning = { field: "file" | "lot" | "kitting"; value: string };

/** バーコードにする値のうち、Code 39 で表せないもの(選んだ種類で使うものだけ。同じ値は1回)。大文字などには直さない。 */
export function barcodeWarnings(slip: IdSlip, sel: Selection): BarcodeWarning[] {
  const found: BarcodeWarning[] = [];
  const add = (field: BarcodeWarning["field"], value: string) => {
    if (value !== "" && !isCode39(value) && !found.some((w) => w.field === field && w.value === value)) found.push({ field, value });
  };
  if (sel.kinds.includes(1)) {
    add("file", slip.file_no);
    for (const lot of sel.lots) add("lot", lot);
  }
  if (sel.kinds.some((k) => k === 1 || k === 2 || k === 3)) add("file", slip.suf);
  if (sel.kinds.includes(4)) add("kitting", slip.kitting_no);
  return found;
}

/** ライン画面に戻る URL(その計画を選んだまま)。 */
export function backUrl(slip: Pick<IdSlip, "line_code" | "kitting_no">): string {
  return `/field/lines/${encodeURIComponent(slip.line_code)}?kitting_no=${encodeURIComponent(slip.kitting_no)}`;
}

/** 識別票のページの URL。 */
export function idSlipsUrl(kittingNo: string): string {
  return `/field/print/id-slips/${encodeURIComponent(kittingNo)}`;
}
