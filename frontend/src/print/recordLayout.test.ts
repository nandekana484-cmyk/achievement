import { describe, expect, it } from "vitest";
import { densityOf, type Face, faceRowCount, firstArticleCells, type Sheet, stepGroups, timeRange, troubleCount } from "./recordLayout";
import { completedText, filterQuery, linesText, linkScreenUrl, recordUrl } from "./recordList";
import { fill, RECORD_TEXT } from "./recordTexts";

const row = (start = "09:00") => ({ date: "10/21", worker: "鈴木", start, end: "09:10" });
const face = (over: Partial<Face> = {}): Face => ({
  kitting_no: "K", line_code: "S", completed: true, setup: [], n1_check: [], production: [], xray: [], cleanup: [], first_article: [],
  good_total: 0, troubles: [], ...over,
});
const sheet = (lots: number, s1: Face | null, s2: Face | null): Sheet => ({
  header: { approver: "", checker: "", author: "", revision_date: "", version: "" }, file_no: "0722", product_name: "基板",
  lots: Array.from({ length: lots }, (_, i) => ({ lot_no: `L${i}`, produced: 1, cumulative: 1, ordered: 1 })),
  qty_differs: [], side1: s1, side2: s2, side2_unlinked: false, side2_kitting_no: null,
});

describe("工程の行", () => {
  it("記録が無くても、様式の基本の行数(生産は3行)を空欄で出す", () => {
    expect(stepGroups(null).map((g) => [g.key, g.rows.length])).toEqual([["setup", 1], ["n1_check", 1], ["production", 3], ["xray", 1], ["cleanup", 1]]);
  });

  it("同じ工程の記録が基本の行より多ければ、記録ごとに行を足す", () => {
    const g = stepGroups(face({ production: Array.from({ length: 6 }, () => row()), setup: [row(), row()] }));
    expect(g.find((x) => x.key === "production")!.rows.length).toBe(6);
    expect(g.find((x) => x.key === "setup")!.rows.length).toBe(2);
    expect(g.find((x) => x.key === "production")!.rows.every(Boolean)).toBe(true);
  });

  it("記録の少ない行は空欄(null)で埋める", () => {
    expect(stepGroups(face({ production: [row()] })).find((x) => x.key === "production")!.rows.map(Boolean)).toEqual([true, false, false]);
  });
});

describe("初品確認", () => {
  it("1〜4に日付と作業者名を入れる", () => {
    expect(firstArticleCells(face({ first_article: [row()] }))).toEqual({ cells: ["10/21 鈴木", "", "", ""], more: 0 });
  });

  it("4つより多いときは、4つ目までと残りの件数", () => {
    const r = firstArticleCells(face({ first_article: Array.from({ length: 6 }, () => row()) }));
    expect(r.cells.every(Boolean)).toBe(true);
    expect(r.more).toBe(2);
  });
});

describe("トラブルと行の詰め具合", () => {
  it("トラブルの行は最低2行、多ければ足す", () => {
    expect(troubleCount(null)).toBe(2);
    expect(troubleCount(face({ troubles: Array.from({ length: 5 }, () => ({ name: "x", start: "09:00", end: null })) }))).toBe(5);
  });

  it("時間は HH:MM〜HH:MM。終了していなければ開始だけ", () => {
    expect(timeRange("09:00", "09:30")).toBe("09:00〜09:30");
    expect(timeRange("09:00", null)).toBe("09:00〜");
  });

  it("行が少なければ通常、多ければ詰める(ロット10個・生産の区切り6つ・付帯作業5件でも、最小の文字の段まで)", () => {
    expect(densityOf(sheet(1, face(), face()))).toBe("normal");
    const busy = (n: number) => face({ production: Array.from({ length: n }, () => row()), troubles: Array.from({ length: 5 }, () => ({ name: "x", start: "09:00", end: "09:05" })) });
    expect(faceRowCount(busy(6))).toBe(10 + 2 + 5); // 工程10行 + 生産台数・初品確認 + トラブル5行
    expect(["dense", "tight"]).toContain(densityOf(sheet(10, busy(6), busy(6))));
  });
});

describe("文言", () => {
  it("日本語とベトナム語がどちらも入っている", () => {
    for (const [key, text] of Object.entries(RECORD_TEXT)) {
      expect(text.ja.trim(), key).not.toBe("");
      expect(text.vi.trim(), key).not.toBe("");
    }
  });

  it("差し込み", () => {
    expect(fill("ほか {count} 件", { count: 2 })).toBe("ほか 2 件");
    expect(fill("{x}", {})).toBe("{x}");
  });
});

describe("一覧", () => {
  it("完了日時は M/D HH:MM", () => {
    expect(completedText("2026-10-21T09:05:00+09:00")).toBe("10/21 09:05");
  });

  it("絞り込みは空欄を送らない", () => {
    expect(filterQuery({ line: "", kitting: " ", lot: "" })).toEqual({});
    expect(filterQuery({ line: "S", kitting: " 0722 ", lot: "L1" })).toEqual({ line: "S", kitting_no: "0722", lot_no: "L1" });
  });

  it("URL とラインの列", () => {
    expect(recordUrl("0722-2-U-261014-32", "S")).toBe("/field/print/production-record/0722-2-U-261014-32?line=S");
    expect(linkScreenUrl("U", "0722-2-U-261014-32")).toBe("/field/lines/U?kitting_no=0722-2-U-261014-32");
    expect(linesText({ side1_line: "S", side2_line: "U" })).toBe("S / U");
    expect(linesText({ side1_line: "S", side2_line: "S" })).toBe("S");
    expect(linesText({ side1_line: null, side2_line: "U" })).toBe("U");
  });
});
