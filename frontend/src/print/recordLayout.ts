// 生産記録票の行の組み立て(React に依存しない)。行の数は、記録の数に合わせて足す。詳細: docs/design/production-record.md
import type { components } from "../api/schema";
import { type RecordTextKey, TIME_RANGE_SEPARATOR } from "./recordTexts";

export type Sheet = components["schemas"]["RecordSheetOut"];
export type Face = components["schemas"]["FaceOut"];
export type StepRow = components["schemas"]["StepRowOut"];

export const FIRST_ARTICLE_CELLS = 4;
export const MIN_TROUBLE_ROWS = 2;

export type StepKey = "setup" | "n1_check" | "production" | "xray" | "cleanup";
export type StepGroup = { key: StepKey; label: RecordTextKey; rows: (StepRow | null)[] };

// 様式の基本の行数。記録がこれより多ければ行を足す(生産は基本3行)
const STEPS: { key: StepKey; label: RecordTextKey; min: number }[] = [
  { key: "setup", label: "setup", min: 1 },
  { key: "n1_check", label: "n1Check", min: 1 },
  { key: "production", label: "production", min: 3 },
  { key: "xray", label: "xray", min: 1 },
  { key: "cleanup", label: "cleanup", min: 1 },
];

/** 工程ごとの行(記録が無い行は null = 空欄)。同じ工程の記録は1件で1行。 */
export function stepGroups(face: Face | null): StepGroup[] {
  return STEPS.map(({ key, label, min }) => {
    const records: StepRow[] = face ? face[key] : [];
    const rows: (StepRow | null)[] = [...records];
    while (rows.length < min) rows.push(null);
    return { key, label, rows };
  });
}

/** 初品確認の1〜4。日付と作業者名。4つより多いときは、4つ目までを出して残りの件数を返す。 */
export function firstArticleCells(face: Face | null): { cells: string[]; more: number } {
  const records = face?.first_article ?? [];
  const cells = Array.from({ length: FIRST_ARTICLE_CELLS }, (_, i) => (records[i] ? `${records[i].date} ${records[i].worker}` : ""));
  return { cells, more: Math.max(0, records.length - FIRST_ARTICLE_CELLS) };
}

export function troubleCount(face: Face | null): number {
  return Math.max(MIN_TROUBLE_ROWS, face?.troubles.length ?? 0);
}

export function timeRange(start: string, end: string | null): string {
  return `${start}${TIME_RANGE_SEPARATOR}${end ?? ""}`;
}

/** 面ごとの行の数の合計(見出しは数えない)。 */
export function faceRowCount(face: Face | null): number {
  return stepGroups(face).reduce((n, g) => n + g.rows.length, 0) + 1 + 1 + troubleCount(face);
}

export type Density = "normal" | "dense" | "tight";

/**
 * 1枚の A4 に収めるための詰め具合。行が多いときは行の高さと文字を縮める(文字は最小 8px)。
 * 行数 = ロットの行 + 両面の行。
 */
export function densityOf(sheet: Sheet): Density {
  const rows = sheet.lots.length + faceRowCount(sheet.side1) + faceRowCount(sheet.side2);
  if (rows > 46) return "tight";
  if (rows > 36) return "dense";
  return "normal";
}
