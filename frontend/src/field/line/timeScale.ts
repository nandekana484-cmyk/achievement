// タイムテーブルの時刻と位置の変換。日付は日本時間の YYYY-MM-DD、時刻は +09:00 付きの ISO 文字列。
// 端末の時間帯に関係なく日本時間で計算する。

export const DAY_MINUTES = 24 * 60;
const JST_OFFSET_MS = 9 * 60 * 60 * 1000;

/** その日の 0:00(日本時間)のミリ秒。 */
export function dayStartMs(date: string): number {
  return Date.parse(`${date}T00:00:00+09:00`);
}

/** その日の 0:00 からの分(範囲外の値もそのまま返す)。 */
export function minutesInDay(time: string | number, date: string): number {
  const ms = typeof time === "number" ? time : Date.parse(time);
  return (ms - dayStartMs(date)) / 60000;
}

export function minutesToY(minutes: number, pxPerHour: number): number {
  return (minutes / 60) * pxPerHour;
}

export function clampMinutes(m: number): number {
  return Math.min(Math.max(m, 0), DAY_MINUTES);
}

export type Span = { top: number; height: number; startMin: number; endMin: number };

/**
 * 開始〜終了をその日の位置にする。終了が空(作業中)なら nowMs まで伸ばす。
 * その日に重ならなければ(0:00 ちょうどに終わるものも含む)null。高さは最低 minHeight にする(短い記録も見えるように)。
 */
export function spanFor(
  start: string, end: string | null | undefined, date: string, nowMs: number, pxPerHour: number, minHeight = 0,
): Span | null {
  const s = minutesInDay(start, date);
  const e = end ? minutesInDay(end, date) : Math.max(s, minutesInDay(nowMs, date));
  if (e <= 0 || s >= DAY_MINUTES) return null;
  const startMin = clampMinutes(s);
  const endMin = clampMinutes(e);
  const top = minutesToY(startMin, pxPerHour);
  return { top, height: Math.max(minutesToY(endMin - startMin, pxPerHour), minHeight), startMin, endMin };
}

/** 時刻を「HH:MM」(日本時間)にする。 */
export function formatHM(time: string | number): string {
  const ms = (typeof time === "number" ? time : Date.parse(time)) + JST_OFFSET_MS;
  const d = new Date(ms);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** 経過時間を「1時間05分」「12分」の形にする。 */
export function formatElapsed(fromMs: number, nowMs: number): string {
  const total = Math.max(0, Math.floor((nowMs - fromMs) / 60000));
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}時間${String(m).padStart(2, "0")}分` : `${m}分`;
}

/** 今日(日本時間)の YYYY-MM-DD。 */
export function todayJst(nowMs: number): string {
  return new Date(nowMs + JST_OFFSET_MS).toISOString().slice(0, 10);
}

/**
 * 重なる区間を横に並べるための列(レーン)を決める。返り値は区間ごとのレーン番号と、レーンの数。
 * 開始の早い順に、空いている一番左のレーンに入れる。
 */
export function assignLanes(items: { startMin: number; endMin: number }[]): { lanes: number[]; laneCount: number } {
  const order = items.map((_, i) => i).sort((a, b) => items[a].startMin - items[b].startMin || a - b);
  const laneEnds: number[] = [];
  const lanes = new Array<number>(items.length).fill(0);
  for (const i of order) {
    let lane = laneEnds.findIndex((endMin) => endMin <= items[i].startMin);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(0);
    }
    laneEnds[lane] = Math.max(items[i].endMin, items[i].startMin + 1);
    lanes[i] = lane;
  }
  return { lanes, laneCount: Math.max(1, laneEnds.length) };
}
