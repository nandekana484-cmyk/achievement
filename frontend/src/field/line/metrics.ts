// ライン画面の上部に出す効率と進捗率の整え方(計算はサーバー。詳細: docs/design/metrics.md)。
import type { Board } from "../../shared/api";
import { formatPercent } from "./steps";

export type ProgressItem = { kittingNo: string; text: string; over: boolean };

/** 生産中の計画ごとの進捗率。100%を超えたものは over(色で分ける)。計画の時間が無ければ「—」。 */
export function progressItems(plans: Board["plans"]): ProgressItem[] {
  return plans
    .filter((p) => p.in_progress)
    .map((p) => ({ kittingNo: p.plan.kitting_no, text: formatPercent(p.progress), over: (p.progress ?? 0) > 1 }));
}

/** 効率の計算から外した計画の件数(0なら出さない)。 */
export function excludedCount(board: Pick<Board, "efficiency"> | null): number {
  return board?.efficiency.excluded ?? 0;
}
