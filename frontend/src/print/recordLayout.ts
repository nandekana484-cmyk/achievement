// 生産記録票の行の組み立て(React に依存しない)。様式の基本の行数に、記録の数に合わせて行を足す。
// 様式: docs/design/forms/production-record-ver02.html。詳細: docs/design/production-record.md
import type { components } from "../api/schema";
import { type RecordTextKey, TIME_RANGE_SEPARATOR } from "./recordTexts";

export type Sheet = components["schemas"]["RecordSheetOut"];
export type Face = components["schemas"]["FaceOut"];
export type StepRow = components["schemas"]["StepRowOut"];

export type Lot = components["schemas"]["LotRowOut"];

export const MIN_LOT_ROWS = 6; // 様式のロットの行
export const GRID_ROWS = 4; // 初品確認の番号 1〜4 が並ぶ行数(生産3 + X線検査1)

export type StepKey = "setup" | "n1_check" | "production" | "xray" | "cleanup";
/** 右の3列(生産台数、初品確認の番号、記入欄)の種類。生産台数の欄は生産の行だけ。詳細: docs/design/production-record.md */
export type RightCells = "blank" | "labels" | "grid" | "tail";

export type RowSpec = { key: StepKey; label: RecordTextKey; rec: StepRow | null; right: RightCells; gridIndex: number };

const MIN_ROWS: Record<StepKey, number> = { setup: 1, n1_check: 1, production: 3, xray: 1, cleanup: 1 };
const LABEL: Record<StepKey, RecordTextKey> = { setup: "setup", n1_check: "n1Check", production: "production", xray: "xray", cleanup: "cleanup" };

function recordsOf(face: Face | null, key: StepKey): (StepRow | null)[] {
  const rows: (StepRow | null)[] = [...(face ? face[key] : [])];
  while (rows.length < MIN_ROWS[key]) rows.push(null);
  return rows;
}

/** 面の明細の行。段取り、マスターチェック、生産、X線検査、片付けの順で、同じ工程の記録は記録ごとに1行。 */
export function faceRows(face: Face | null): RowSpec[] {
  const spec = (key: StepKey, rec: StepRow | null, right: RightCells, gridIndex = -1): RowSpec =>
    ({ key, label: LABEL[key], rec, right, gridIndex });
  const rows: RowSpec[] = recordsOf(face, "setup").map((r) => spec("setup", r, "blank"));
  rows.push(...recordsOf(face, "n1_check").map((r, i) => spec("n1_check", r, i === 0 ? "labels" : "blank")));
  const middle = [...recordsOf(face, "production").map((r) => ["production", r] as const), ...recordsOf(face, "xray").map((r) => ["xray", r] as const)];
  middle.forEach(([key, r], i) => rows.push(i < GRID_ROWS ? spec(key, r, "grid", i) : spec(key, r, "tail")));
  rows.push(...recordsOf(face, "cleanup").map((r) => spec("cleanup", r, "tail")));
  return rows;
}

/** 初品確認の記入欄の中身。入りきらないとき(capacity 行)は、最後の行を「ほか N 件」にする。 */
export function firstArticleLines(face: Face | null, capacity: number): { lines: string[]; more: number } {
  const all = (face?.first_article ?? []).map((r) => `${r.date} ${r.worker}`);
  if (all.length <= capacity) return { lines: all, more: 0 };
  const shown = Math.max(0, capacity - 1);
  return { lines: all.slice(0, shown), more: all.length - shown };
}

/** 数量 A に実績を添えるか(Aの面の計画が完了していて、実績が A と違うとき)。 */
export function actualDiffers(lot: Lot): boolean {
  return lot.actual != null && lot.produced != null && lot.actual !== lot.produced;
}

/** 数量の欄の表示。実績が A と違うとき、A と B に取消線を引き、実績と「B - A + 実績」を添える(C は変えない。印刷だけの表示)。 */
export type QuantityView = { a: number | null; b: number | null; c: number | null; actual: number | null; newB: number | null };

export function quantityView(lot: Lot): QuantityView {
  const base = { a: lot.produced, b: lot.cumulative, c: lot.ordered };
  if (!actualDiffers(lot)) return { ...base, actual: null, newB: null };
  const actual = lot.actual as number;
  return { ...base, actual, newB: lot.cumulative == null ? null : lot.cumulative - (lot.produced as number) + actual };
}

export function timeRange(start: string, end: string | null): string {
  return `${start}${TIME_RANGE_SEPARATOR}${end ?? ""}`;
}

/** ロットの行の数(様式は6行。多ければ足す)。 */
export function lotRowCount(sheet: Sheet): number {
  return Math.max(MIN_LOT_ROWS, sheet.lots.length);
}

export type Density = "normal" | "dense" | "tight" | "tiny";

/** 詰め具合の順。収まらないときは次へ進める(先に行の高さ、あとで文字。最小 8px)。 */
export const DENSITIES: Density[] = ["normal", "dense", "tight", "tiny"];

// 行の高さの倍率(record.css の --k と同じ)
const HEIGHT_RATIO: Record<Density, number> = { normal: 1, dense: 0.8, tight: 0.65, tiny: 0.5 };

export const ROW_MM = 9.5; // 作業の1行の高さ(record.css の --row)
export const LINE_PX = 12; // 初品確認の枠の1行の高さ(record.css の --line)
const PX_PER_MM = 96 / 25.4;

/** 初品確認の枠に入る行数。 */
export function boxCapacity(d: Density): number {
  return Math.max(1, Math.floor((GRID_ROWS * ROW_MM * PX_PER_MM * HEIGHT_RATIO[d]) / LINE_PX));
}

/** 用紙(297mm - 上下の余白 10mm = 287mm ≒ 1085px)に収まる高さの上限(px)。余裕を少し見る。 */
export const MAX_HEIGHT_PX = 1080;

export function nextDensity(d: Density): Density | null {
  return DENSITIES[DENSITIES.indexOf(d) + 1] ?? null;
}

/** 収まらないときの次の詰め具合(収まる、またはこれ以上詰められなければ null)。 */
export function denserIfOverflow(d: Density, heightPx: number): Density | null {
  return heightPx > MAX_HEIGHT_PX ? nextDensity(d) : null;
}
