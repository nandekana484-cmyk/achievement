import { describe, expect, it } from "vitest";
import {
  assignLanes, clockOffset, formatElapsed, formatHM, formatMD, formatMDHM, hourTicks, minutesFrom, minutesToY, spanFor,
} from "./timeScale";

// 稼働日 10/21 の表示範囲: 10/20 20:15 〜 10/22 20:15(48時間)
const ORIGIN = Date.parse("2026-10-20T20:15:00+09:00");
const TOTAL = 48 * 60;
const at = (s: string) => `2026-10-${s}:00+09:00`; // 例: at("21T09:00")

describe("時刻と位置の変換", () => {
  it("表示範囲の始まりからの分", () => {
    expect(minutesFrom(at("20T20:15"), ORIGIN)).toBe(0);
    expect(minutesFrom(at("21T08:15"), ORIGIN)).toBe(720); // 稼働日の始まり
    expect(minutesFrom("2026-10-20T23:15:00Z", ORIGIN)).toBe(720); // UTC で書かれていても同じ時刻
    expect(minutesFrom(at("20T20:00"), ORIGIN)).toBe(-15);
  });

  it("分を位置にする", () => {
    expect(minutesToY(60, 90)).toBe(90);
    expect(minutesToY(720, 60)).toBe(720);
  });

  it("開始〜終了の位置と高さ", () => {
    expect(spanFor(at("21T09:00"), at("21T12:00"), ORIGIN, TOTAL, 0, 60)).toEqual({
      top: 765, height: 180, startMin: 765, endMin: 945, clippedStart: false, clippedEnd: false,
    });
  });

  it("表示範囲からはみ出す分は端で切り、切れたことが分かる", () => {
    expect(spanFor(at("20T18:00"), at("20T22:15"), ORIGIN, TOTAL, 0, 60)).toMatchObject({ top: 0, height: 120, clippedStart: true, clippedEnd: false });
    expect(spanFor(at("22T19:15"), "2026-10-23T02:00:00+09:00", ORIGIN, TOTAL, 0, 60)).toMatchObject({ height: 60, endMin: TOTAL, clippedEnd: true });
  });

  it("表示範囲に重ならないもの・日程が空のものは null", () => {
    expect(spanFor(at("20T18:00"), at("20T20:15"), ORIGIN, TOTAL, 0, 60)).toBeNull(); // 始まりちょうどに終わる
    expect(spanFor(at("22T20:15"), at("22T22:00"), ORIGIN, TOTAL, 0, 60)).toBeNull();
    expect(spanFor(null, null, ORIGIN, TOTAL, 0, 60)).toBeNull();
  });

  it("終了していないものは今まで伸ばす", () => {
    const now = Date.parse(at("21T10:30"));
    expect(spanFor(at("21T10:00"), null, ORIGIN, TOTAL, now, 60)).toMatchObject({ top: 825, height: 30 });
    expect(spanFor(at("21T10:00"), null, ORIGIN, TOTAL, Date.parse(at("21T09:00")), 60)).toMatchObject({ height: 0 }); // 時計のずれで負にしない
  });

  it("短いものも最低の高さにする", () => {
    expect(spanFor(at("21T10:00"), at("21T10:01"), ORIGIN, TOTAL, 0, 60, 30)).toMatchObject({ height: 30 });
  });

  it("毎正時の目盛り(表示範囲の始まりが 20:15 なら 21:00 から)", () => {
    const ticks = hourTicks(ORIGIN, ORIGIN + TOTAL * 60000);
    expect(ticks).toHaveLength(48);
    expect(ticks[0].label).toBe("21:00");
    expect(ticks[3].label).toBe("00:00");
    expect(ticks[47].label).toBe("20:00");
    expect(minutesFrom(ticks[0].ms, ORIGIN)).toBe(45);
  });

  it("時刻・日付・経過時間の表示(端末の時間帯によらず日本時間)", () => {
    expect(formatHM(at("21T08:05"))).toBe("08:05");
    expect(formatHM("2026-10-20T23:30:00Z")).toBe("08:30");
    expect(formatMDHM("2026-10-18T09:00:00+09:00")).toBe("10/18 9:00");
    expect(formatMDHM("2026-10-17T15:05:00Z")).toBe("10/18 0:05");
    expect(formatMD("2026-10-21")).toBe("10/21");
    expect(formatElapsed(0, 12 * 60000)).toBe("12分");
    expect(formatElapsed(0, 65 * 60000)).toBe("1時間05分");
    expect(formatElapsed(1000, 0)).toBe("0分");
  });

  it("サーバーの時計との差(往復の真ん中で比べる)", () => {
    const sent = Date.parse(at("21T10:00"));
    expect(clockOffset(at("21T10:05"), sent, sent + 2000)).toBe(5 * 60000 - 1000);
    expect(clockOffset(at("21T10:00"), sent, sent)).toBe(0);
  });
});

describe("assignLanes", () => {
  it("重ならなければ1列", () => {
    expect(assignLanes([{ startMin: 0, endMin: 60 }, { startMin: 60, endMin: 120 }])).toEqual({ lanes: [0, 0], laneCount: 1 });
  });

  it("重なるものは横に並べ、空いた列は使い回す", () => {
    const r = assignLanes([{ startMin: 480, endMin: 660 }, { startMin: 630, endMin: 750 }, { startMin: 660, endMin: 840 }]);
    expect(r).toEqual({ lanes: [0, 1, 0], laneCount: 2 });
  });

  it("空なら1列", () => {
    expect(assignLanes([])).toEqual({ lanes: [], laneCount: 1 });
  });
});
