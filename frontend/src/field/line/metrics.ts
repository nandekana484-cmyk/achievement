// ライン画面の上部に出す効率の補助(計算はサーバー。詳細: docs/design/metrics.md)。
import type { Board } from "../../shared/api";

/** 効率の計算から外した計画の件数(0なら出さない)。 */
export function excludedCount(board: Pick<Board, "efficiency"> | null): number {
  return board?.efficiency.excluded ?? 0;
}
