// 日報のガントチャートの計算(画面から切り離して vitest でテストする)。上段・下段はそれぞれ12時間。
import type { components } from "../../api/schema";

type Schemas = components["schemas"];
export type DailyReport = Schemas["DailyReportOut"];
export type ReportRow = Schemas["RowOut"];
export type ReportBar = Schemas["BarOut"];
export type Half = Schemas["HalfOut"];

/** 1ページに出す行の数(A4 横向きに、上段と下段の両方が収まる数)。 */
export const ROWS_PER_PAGE = 9;

const HOUR_MS = 3_600_000;
const JST_OFFSET_MS = 9 * HOUR_MS;

/** 行をページに分ける。行が無くても1ページは出す(見出しと空のチャート)。 */
export function paginate<T>(rows: T[], perPage = ROWS_PER_PAGE): T[][] {
  if (rows.length === 0) return [[]];
  const pages = [];
  for (let i = 0; i < rows.length; i += perPage) pages.push(rows.slice(i, i + perPage));
  return pages;
}

/** 棒の位置(段の幅に対する % の left と width)。短い棒も見えるよう、幅は最低 minWidth %。 */
export function barBox(bar: Pick<ReportBar, "start" | "end">, half: Half, minWidth = 0.4): { left: number; width: number } {
  const s = Date.parse(half.start);
  const span = Date.parse(half.end) - s;
  const left = ((Date.parse(bar.start) - s) / span) * 100;
  const width = Math.max(((Date.parse(bar.end) - Date.parse(bar.start)) / span) * 100, minWidth);
  return { left, width: Math.min(width, 100 - left) };
}

/** 時刻を「8:15」の形(日本時間)にする。 */
export function formatTime(ms: number | string): string {
  const d = new Date((typeof ms === "string" ? Date.parse(ms) : ms) + JST_OFFSET_MS);
  return `${d.getUTCHours()}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** 段の1時間ごとの目盛り(左からの % と「8:15」の形の時刻)。両端を含む。 */
export function hourTicks(half: Half): { left: number; label: string }[] {
  const s = Date.parse(half.start);
  const span = Date.parse(half.end) - s;
  const ticks = [];
  for (let ms = s; ms <= Date.parse(half.end); ms += HOUR_MS) ticks.push({ left: ((ms - s) / span) * 100, label: formatTime(ms) });
  return ticks;
}

/** 日時を「2026/10/21 9:05」の形(日本時間)にする。 */
export function formatDateTime(iso: string): string {
  const d = new Date(Date.parse(iso) + JST_OFFSET_MS);
  return `${d.getUTCFullYear()}/${d.getUTCMonth() + 1}/${d.getUTCDate()} ${d.getUTCHours()}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}
