// 計画の検索で使う、表示から分けた判定(完全一致の1件、表示範囲の外か)と、計画の短い説明の文。
import type { Translate } from "../../i18n/translate";
import type { Board, Plan } from "../../shared/api";
import { formatMDHM } from "./timeScale";

/** 比べるための形(全角→半角、英字は大文字、前後の空白なし)。サーバーの検索と同じ考え方。 */
export function foldForMatch(text: string): string {
  return text.normalize("NFKC").toUpperCase().trim();
}

/** キッティングNo.が完全に一致する計画がちょうど1件なら、その計画(Enter でそのまま選ぶ)。 */
export function exactKittingMatch(results: Plan[], query: string): Plan | null {
  const q = foldForMatch(query);
  const hits = results.filter((p) => foldForMatch(p.kitting_no) === q);
  return hits.length === 1 ? hits[0] : null;
}

/** 計画開始〜終了が表示範囲と重ならないか(日程が空の計画も「外」とする)。 */
export function isOutsideDisplay(plan: Plan, board: Pick<Board, "display_start" | "display_end">): boolean {
  if (!plan.planned_start || !plan.planned_end) return true;
  return Date.parse(plan.planned_end) <= Date.parse(board.display_start) || Date.parse(plan.planned_start) >= Date.parse(board.display_end);
}

/** 「表示範囲外の計画です(計画: 10/18 9:00〜)」の文。 */
export function outsideMessage(plan: Plan, t: Translate): string {
  return t("plan.outsideDisplay", { when: plannedFrom(plan, t) });
}

/** 計画開始「10/18 9:00〜」。日程が空なら「日程なし」。 */
export function plannedFrom(plan: Plan, t: Translate): string {
  return plan.planned_start ? t("common.from", { time: formatMDHM(plan.planned_start) }) : t("common.noSchedule");
}

/** 「3ロット・計画数 300・1回目」(ロットが1つなら基板名)。タイムテーブルの枠と検索の結果に出す。 */
export function planSummary(plan: Plan, t: Translate): string {
  const what = plan.lots.length > 1 ? t("unit.lots", { count: plan.lots.length }) : plan.product_name;
  return t("plan.summary", { what, qty: plan.planned_qty, run: t("unit.runNo", { run: plan.run_no }) });
}
