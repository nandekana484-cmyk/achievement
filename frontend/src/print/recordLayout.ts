// 生産記録票の行の組み立て(React に依存しない)。様式の基本の行数に、記録の数に合わせて行を足す。
// 様式: docs/design/forms/production-record-ver02.html。詳細: docs/design/production-record.md
import type { components } from "../api/schema";
import { type RecordTextKey, TIME_RANGE_SEPARATOR } from "./recordTexts";

export type Sheet = components["schemas"]["RecordSheetOut"];
export type Face = components["schemas"]["FaceOut"];
export type StepRow = components["schemas"]["StepRowOut"];

export const FIRST_ARTICLE_CELLS = 4;
export const MIN_LOT_ROWS = 6; // 様式のロットの行
export const GRID_ROWS = 4; // 様式の、生産台数と初品確認 1〜4 が並ぶ行数(生産3 + X線検査1)

export type StepKey = "setup" | "n1_check" | "production" | "xray" | "cleanup";
/** 行の高さの種類。step=段取り・マスターチェック、grid=生産台数と初品確認の欄が並ぶ行、tail=それより後の行。 */
export type RowHeight = "step" | "grid" | "tail";
/** 右の2列: blank=空、labels=「生産台数」「初品確認」の見出し、grid=初品確認の欄(生産台数は先頭の行から4行に渡る)、gray=灰色。 */
export type RightCells = "blank" | "labels" | "grid" | "gray";

export type RowSpec = { key: StepKey; label: RecordTextKey; rec: StepRow | null; height: RowHeight; right: RightCells; gridIndex: number };

const MIN_ROWS: Record<StepKey, number> = { setup: 1, n1_check: 1, production: 3, xray: 1, cleanup: 1 };
const LABEL: Record<StepKey, RecordTextKey> = { setup: "setup", n1_check: "n1Check", production: "production", xray: "xray", cleanup: "cleanup" };

function recordsOf(face: Face | null, key: StepKey): (StepRow | null)[] {
  const rows: (StepRow | null)[] = [...(face ? face[key] : [])];
  while (rows.length < MIN_ROWS[key]) rows.push(null);
  return rows;
}

/**
 * 面の明細の行。段取り、マスターチェック、生産、X線検査、片付けの順で、同じ工程の記録は記録ごとに1行。
 * 様式の「生産/X線検査」の行は、生産とX線検査の別々の行に分けてある。生産とX線検査の先頭4行(基本の行数)が、右の生産台数と初品確認の欄に並ぶ。
 */
export function faceRows(face: Face | null): RowSpec[] {
  const spec = (key: StepKey, rec: StepRow | null, height: RowHeight, right: RightCells, gridIndex = -1): RowSpec =>
    ({ key, label: LABEL[key], rec, height, right, gridIndex });
  const rows: RowSpec[] = recordsOf(face, "setup").map((r) => spec("setup", r, "step", "blank"));
  rows.push(...recordsOf(face, "n1_check").map((r, i) => spec("n1_check", r, "step", i === 0 ? "labels" : "blank")));
  const middle = [...recordsOf(face, "production").map((r) => ["production", r] as const), ...recordsOf(face, "xray").map((r) => ["xray", r] as const)];
  middle.forEach(([key, r], i) => rows.push(i < GRID_ROWS ? spec(key, r, "grid", "grid", i) : spec(key, r, "tail", "gray")));
  rows.push(...recordsOf(face, "cleanup").map((r) => spec("cleanup", r, "tail", "gray")));
  return rows;
}

/** 初品確認の1〜4。日付と作業者名。4つより多いときは、4つ目までを出して残りの件数を返す。 */
export function firstArticleCells(face: Face | null): { cells: string[]; more: number } {
  const records = face?.first_article ?? [];
  const cells = Array.from({ length: FIRST_ARTICLE_CELLS }, (_, i) => (records[i] ? `${records[i].date} ${records[i].worker}` : ""));
  return { cells, more: Math.max(0, records.length - FIRST_ARTICLE_CELLS) };
}

export function timeRange(start: string, end: string | null): string {
  return `${start}${TIME_RANGE_SEPARATOR}${end ?? ""}`;
}

/** ロットの行の数(様式は6行。多ければ足す)。 */
export function lotRowCount(sheet: Sheet): number {
  return Math.max(MIN_LOT_ROWS, sheet.lots.length);
}

export type Density = "normal" | "dense" | "tight";

/** 詰め具合の順。行が多くて1枚に収まらないときは、次へ進めて行の高さと文字を縮める(文字は最小 8px)。 */
export const DENSITIES: Density[] = ["normal", "dense", "tight"];

/** 用紙(A4縦から余白 8mm を除いた高さ約 1062px)に収まる高さの上限(px)。折り返しの余裕を少し見る。 */
export const MAX_HEIGHT_PX = 1050;

/** 次の詰め具合(これ以上詰められなければ null)。 */
export function nextDensity(d: Density): Density | null {
  return DENSITIES[DENSITIES.indexOf(d) + 1] ?? null;
}

/** 今の高さで収まっているか、収まらないなら次の詰め具合を返す(収まる、またはこれ以上詰められなければ null)。 */
export function denserIfOverflow(d: Density, heightPx: number): Density | null {
  return heightPx > MAX_HEIGHT_PX ? nextDensity(d) : null;
}
