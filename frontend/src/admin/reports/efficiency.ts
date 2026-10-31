// 日報の効率の表示(計算はサーバー。画面のバーと同じ値。詳細: docs/design/metrics.md)。
import { formatPercent } from "../../field/line/steps";
import { type AdminKey, at } from "../messages";
import type { DailyReport } from "./gantt";

const KNOWN = new Set([
  "no_row", "no_takt", "tsv_not_found", "ambiguous_tsv", "read_error", "no_k_row", "multi_k", "code_not_in_master", "teitori_invalid",
]);

/** 外した理由(丁取りの status、no_row、no_takt)の日本語。知らない status は「不明な状態」にして値を添える。 */
export function reasonLabel(reason: string): string {
  return KNOWN.has(reason) ? at(`reason.${reason}` as AdminKey) : at("reason.unknown", { status: reason });
}

export function efficiencyText(report: Pick<DailyReport, "efficiency">): string {
  return at("report.efficiency", { value: formatPercent(report.efficiency.efficiency) });
}

/** 外した計画の件数と理由ごとの件数。外した計画が無ければ null。 */
export function excludedText(report: Pick<DailyReport, "efficiency">): string | null {
  const e = report.efficiency;
  if (e.excluded === 0) return null;
  const reasons = e.reasons.map((r) => at("report.excludedReason", { reason: reasonLabel(r.reason), count: r.count })).join(at("listSeparator"));
  return at("report.excluded", { count: e.excluded, reasons });
}
