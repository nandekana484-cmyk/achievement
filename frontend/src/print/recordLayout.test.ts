import { describe, expect, it } from "vitest";
import { denserIfOverflow, type Face, faceRows, firstArticleCells, lotRowCount, type Sheet, timeRange } from "./recordLayout";
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
const keys = (f: Face | null) => faceRows(f).map((r) => r.key);

describe("明細の行(様式: 生産3行 + X線検査1行が、生産台数と初品確認の4行に並ぶ)", () => {
  it("記録が無くても、様式の基本の行(段取り1、マスターチェック1、生産3、X線検査1、片付け1)を空欄で出す", () => {
    expect(keys(null)).toEqual(["setup", "n1_check", "production", "production", "production", "xray", "cleanup"]);
    const rows = faceRows(null);
    expect(rows.map((r) => r.right)).toEqual(["blank", "labels", "grid", "grid", "grid", "grid", "gray"]);
    expect(rows.filter((r) => r.right === "grid").map((r) => r.gridIndex)).toEqual([0, 1, 2, 3]);
  });

  it("生産の区切りが多ければ、記録ごとに行を足す(4行目より後は灰色の右側)", () => {
    const rows = faceRows(face({ production: Array.from({ length: 6 }, () => row()) }));
    expect(rows.filter((r) => r.key === "production")).toHaveLength(6);
    expect(rows.filter((r) => r.right === "grid")).toHaveLength(4);
    expect(rows.filter((r) => r.height === "tail").map((r) => r.key)).toEqual(["production", "production", "xray", "cleanup"]);
  });

  it("同じ工程の記録が複数あれば、記録ごとに行を足す。X線検査と段取りも同じ", () => {
    expect(keys(face({ setup: [row(), row()], xray: [row(), row()] })).filter((k) => k === "setup" || k === "xray")).toEqual(["setup", "setup", "xray", "xray"]);
  });

  it("生産台数と初品確認の見出しは、マスターチェックの先頭の行", () => {
    const rows = faceRows(face({ n1_check: [row(), row()] }));
    expect(rows.filter((r) => r.right === "labels")).toHaveLength(1);
    expect(rows.find((r) => r.right === "labels")!.key).toBe("n1_check");
  });

  it("記録のある行は rec を持ち、無い行は null", () => {
    expect(faceRows(face({ production: [row()] })).filter((r) => r.key === "production").map((r) => Boolean(r.rec))).toEqual([true, false, false]);
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

describe("ロットの行と、行の詰め具合", () => {
  it("ロットの行は様式の6行。多ければ足す", () => {
    expect(lotRowCount(sheet(1, null, null))).toBe(6);
    expect(lotRowCount(sheet(10, null, null))).toBe(10);
  });

  it("時間は HH:MM～HH:MM。終了していなければ開始だけ", () => {
    expect(timeRange("09:00", "09:30")).toBe("09:00～09:30");
    expect(timeRange("09:00", null)).toBe("09:00～");
  });

  it("収まらないときだけ、次の詰め具合へ進める(最後まで進んだら止める)", () => {
    expect(denserIfOverflow("normal", 900)).toBeNull();
    expect(denserIfOverflow("normal", 1200)).toBe("dense");
    expect(denserIfOverflow("dense", 1200)).toBe("tight");
    expect(denserIfOverflow("tight", 1200)).toBeNull();
  });
});

describe("文言", () => {
  it("日本語は必ず入る。ベトナム語は様式にある欄だけ", () => {
    for (const [key, text] of Object.entries(RECORD_TEXT)) expect(text.ja.trim(), key).not.toBe("");
    expect(RECORD_TEXT.title.vi).toBe("BIỂU GHI CHÉP SẢN XUẤT");
    expect(RECORD_TEXT.worker.vi).toBe("TÊN NGƯỜI THAO TÁC");
    for (const k of ["setup", "n1Check", "production", "xray", "cleanup", "goodTotal", "firstArticle", "line", "solderLot", "bondLot"] as const) {
      expect(RECORD_TEXT[k].vi, k).not.toBe("");
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
