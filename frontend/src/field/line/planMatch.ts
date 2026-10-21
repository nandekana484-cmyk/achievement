// 計画の検索で使う、表示から分けた判定(完全一致の1件、表示範囲の外か)。
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
export function outsideMessage(plan: Plan): string {
  return `表示範囲外の計画です(計画: ${plan.planned_start ? `${formatMDHM(plan.planned_start)}〜` : "日程なし"})`;
}
