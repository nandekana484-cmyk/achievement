// タイムテーブルの時刻と位置の変換。基準は表示範囲の始まり(稼働日の始まりの12時間前)。
// 時刻は +09:00 付きの ISO 文字列かミリ秒。端末の時間帯と表示言語に関係なく、日本時間の24時間表記で表示する。
import type { Translate } from "../../i18n/translate";

const JST_OFFSET_MS = 9 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

const toMs = (time: string | number) => (typeof time === "number" ? time : Date.parse(time));

/** 基準からの分(範囲外の値もそのまま返す)。 */
export function minutesFrom(time: string | number, originMs: number): number {
  return (toMs(time) - originMs) / 60000;
}

export function minutesToY(minutes: number, pxPerHour: number): number {
  return (minutes / 60) * pxPerHour;
}

export type Span = { top: number; height: number; startMin: number; endMin: number; clippedStart: boolean; clippedEnd: boolean };

/**
 * 開始〜終了を、基準から totalMinutes 分の範囲の位置にする。終了が空(作業中)なら nowMs まで伸ばす。
 * 範囲に重ならなければ(範囲の始まりちょうどに終わるものも含む)null。範囲からはみ出す分は切り、印のための旗を立てる。
 * 高さは最低 minHeight にする(短い記録も見えるように)。
 */
export function spanFor(
  start: string | null | undefined, end: string | null | undefined,
  originMs: number, totalMinutes: number, nowMs: number, pxPerHour: number, minHeight = 0,
): Span | null {
  if (!start) return null;
  const s = minutesFrom(start, originMs);
  const e = end ? minutesFrom(end, originMs) : Math.max(s, minutesFrom(nowMs, originMs));
  if (e <= 0 || s >= totalMinutes) return null;
  const startMin = Math.max(s, 0);
  const endMin = Math.min(e, totalMinutes);
  return {
    top: minutesToY(startMin, pxPerHour),
    height: Math.max(minutesToY(endMin - startMin, pxPerHour), minHeight),
    startMin, endMin, clippedStart: s < 0, clippedEnd: e > totalMinutes,
  };
}

/** 範囲の中のちょうどの時刻(日本時間の毎正時)と、その表示(「21:00」)。 */
export function hourTicks(originMs: number, endMs: number): { ms: number; label: string }[] {
  const ticks = [];
  for (let ms = Math.ceil((originMs + JST_OFFSET_MS) / HOUR_MS) * HOUR_MS - JST_OFFSET_MS; ms <= endMs; ms += HOUR_MS) {
    ticks.push({ ms, label: formatHM(ms) });
  }
  return ticks;
}

/** 時刻を「HH:MM」(日本時間)にする。 */
export function formatHM(time: string | number): string {
  const d = new Date(toMs(time) + JST_OFFSET_MS);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** 時刻を「10/18 9:00」(日本時間)にする。 */
export function formatMDHM(time: string | number): string {
  const d = new Date(toMs(time) + JST_OFFSET_MS);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()} ${d.getUTCHours()}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** 日付を「10/21」にする(YYYY-MM-DD から)。 */
export function formatMD(date: string): string {
  const [, m, d] = date.split("-").map(Number);
  return `${m}/${d}`;
}

/** 経過時間を「1時間05分」「12分」の形にする(単位は選んだ言語)。 */
export function formatElapsed(fromMs: number, nowMs: number, t: Translate): string {
  const total = Math.max(0, Math.floor((nowMs - fromMs) / 60000));
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? t("time.elapsedHours", { h, m: String(m).padStart(2, "0") }) : t("time.elapsedMinutes", { m });
}

/**
 * サーバーの時計とタブレットの時計の差(サーバー − タブレット)。往復の真ん中でサーバーが時刻を付けたとみなす。
 */
export function clockOffset(serverTime: string, sentMs: number, receivedMs: number): number {
  return Date.parse(serverTime) - (sentMs + receivedMs) / 2;
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

/** ミリ秒を、サーバーに送る形(日本時間の +09:00 付きの ISO 文字列。秒まで)にする。 */
export function toJstIso(ms: number): string {
  return new Date(Math.floor(ms / 1000) * 1000 + JST_OFFSET_MS).toISOString().replace(/\.\d{3}Z$/, "+09:00");
}
