// 効率と進捗率の表示(画面と印刷のすべてでこの1か所を使う)。200%を超える値は、数を見せずに「***%」と出す。
// CSV と API の値は変えない(数のまま)。詳細: docs/design/metrics.md
/** これを超えると「***%」にする割合(200%)。 */
export const PERCENT_DISPLAY_MAX = 2;
export const PERCENT_HIDDEN = "***%";

/** 割合を「50%」の形にする。空なら「—」。200%ちょうどまでは数、200%を超えたら「***%」。 */
export function formatPercent(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined) return "—";
  return ratio > PERCENT_DISPLAY_MAX ? PERCENT_HIDDEN : `${Math.round(ratio * 100)}%`;
}
