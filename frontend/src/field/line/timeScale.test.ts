import { describe, expect, it } from "vitest";
import {
  assignLanes, DAY_MINUTES, dayStartMs, formatElapsed, formatHM, minutesInDay, minutesToY, spanFor, todayJst,
} from "./timeScale";

const DATE = "2026-10-21";
const at = (hm: string, date = DATE) => `${date}T${hm}:00+09:00`;

describe("時刻と位置の変換", () => {
  it("その日の 0:00(日本時間)からの分", () => {
    expect(minutesInDay(at("00:00"), DATE)).toBe(0);
    expect(minutesInDay(at("09:30"), DATE)).toBe(570);
    expect(minutesInDay("2026-10-21T00:30:00Z", DATE)).toBe(570); // UTC で書かれていても日本時間で数える
    expect(minutesInDay(at("23:00", "2026-10-20"), DATE)).toBe(-60);
    expect(minutesInDay(dayStartMs(DATE) + 90 * 60000, DATE)).toBe(90);
  });

  it("分を位置にする", () => {
    expect(minutesToY(60, 90)).toBe(90);
    expect(minutesToY(570, 90)).toBe(855);
  });

  it("開始〜終了の位置と高さ", () => {
    expect(spanFor(at("09:00"), at("12:00"), DATE, 0, 60)).toEqual({ top: 540, height: 180, startMin: 540, endMin: 720 });
  });

  it("前の日から続くもの・次の日まで続くものは、その日の範囲で切る", () => {
    expect(spanFor(at("22:00", "2026-10-20"), at("01:00"), DATE, 0, 60)).toMatchObject({ top: 0, height: 60 });
    expect(spanFor(at("23:00"), at("02:00", "2026-10-22"), DATE, 0, 60)).toMatchObject({ top: 1380, height: 60, endMin: DAY_MINUTES });
  });

  it("その日に重ならないものは null(0:00 ちょうどに終わるものも)", () => {
    expect(spanFor(at("20:00", "2026-10-20"), at("00:00"), DATE, 0, 60)).toBeNull();
    expect(spanFor(at("09:00", "2026-10-22"), at("10:00", "2026-10-22"), DATE, 0, 60)).toBeNull();
  });

  it("終了していないものは今まで伸ばす", () => {
    const now = Date.parse(at("10:30"));
    expect(spanFor(at("10:00"), null, DATE, now, 60)).toMatchObject({ top: 600, height: 30 });
    expect(spanFor(at("10:00"), null, DATE, Date.parse(at("09:00")), 60)).toMatchObject({ height: 0 }); // 時計のずれで今より後でも負にしない
  });

  it("短いものも最低の高さにする", () => {
    expect(spanFor(at("10:00"), at("10:01"), DATE, 0, 60, 22)).toMatchObject({ height: 22 });
  });

  it("時刻と経過時間の表示(端末の時間帯によらず日本時間)", () => {
    expect(formatHM(at("08:05"))).toBe("08:05");
    expect(formatHM("2026-10-20T23:30:00Z")).toBe("08:30");
    expect(formatElapsed(0, 12 * 60000)).toBe("12分");
    expect(formatElapsed(0, 65 * 60000)).toBe("1時間05分");
    expect(formatElapsed(1000, 0)).toBe("0分");
    expect(todayJst(Date.parse("2026-10-20T15:30:00Z"))).toBe("2026-10-21");
  });
});

describe("assignLanes", () => {
  it("重ならなければ1列", () => {
    expect(assignLanes([{ startMin: 0, endMin: 60 }, { startMin: 60, endMin: 120 }])).toEqual({ lanes: [0, 0], laneCount: 1 });
  });

  it("重なるものは横に並べ、空いた列は使い回す", () => {
    const r = assignLanes([
      { startMin: 480, endMin: 660 }, // 8:00-11:00
      { startMin: 630, endMin: 750 }, // 10:30-12:30(重なる)
      { startMin: 660, endMin: 840 }, // 11:00-14:00(1列目が空く)
    ]);
    expect(r).toEqual({ lanes: [0, 1, 0], laneCount: 2 });
  });

  it("空なら1列", () => {
    expect(assignLanes([])).toEqual({ lanes: [], laneCount: 1 });
  });
});
