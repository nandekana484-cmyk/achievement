import { describe, expect, it } from "vitest";
import { applyBody, applyMeta, carrySummary, defaultSelection, type ImportSheet, overwriteCount, toggle } from "./importLogic";

const sheet = (over: Partial<ImportSheet>): ImportSheet => ({
  sheet_name: "0722", file_no: "0722", status: "new", reason: null, row_count: 3, manager_no: "M", overwrites_manual: false, current_version: null, carried: 0, lost: [], changes: [], changes_more: 0, ...over,
});
const sheets = [
  sheet({ sheet_name: "722" }), sheet({ sheet_name: "0800", file_no: "0800", status: "changed", overwrites_manual: true }),
  sheet({ sheet_name: "0900", file_no: "0900", status: "unchanged" }), sheet({ sheet_name: "Sheet1", file_no: null, status: "skipped", reason: "飛ばした" }),
  sheet({ sheet_name: "0960", file_no: "0960", status: "error", reason: "見出し" }),
];

describe("Excel 取り込みの選び方", () => {
  it("初期値は新規と変更ありだけ", () => {
    expect(defaultSelection(sheets)).toEqual(["0722", "0800"]);
  });

  it("選び直せるのは登録できるシートだけ(変更なし・飛ばした・エラーは選べない)", () => {
    expect(toggle(sheets, ["0722", "0800"], "0722")).toEqual(["0800"]);
    expect(toggle(sheets, ["0800"], "0722")).toEqual(["0722", "0800"]);
    expect(toggle(sheets, ["0722"], "0900")).toEqual(["0722"]);
  });

  it("選んだシートのうち、管理画面で直した内容を上書きするものの数", () => {
    expect(overwriteCount(sheets, ["0722", "0800"])).toBe(1);
    expect(overwriteCount(sheets, ["0722"])).toBe(0);
  });

  it("登録の指定は、選んだファイルNo.・確かめたブックの SHA-256・確かめたときの状態と版", () => {
    const withVersion = sheets.map((s) => (s.file_no === "0800" ? { ...s, current_version: 3 } : s));
    expect(applyMeta({ sha256: "ab".repeat(32), sheets: withVersion }, ["0722", "0800"])).toEqual({
      file_nos: ["0722", "0800"], sha256: "ab".repeat(32), states: { "0722": { status: "new", version: 0 }, "0800": { status: "changed", version: 3 } },
    });
  });

  it("引き継いだ行と、引き継げずに消えるものの合計(選んだシートだけ)", () => {
    const withCarry = [sheet({ file_no: "0001", carried: 2, lost: [{ row: 3, name: "旧", name_vi: "v", link: "run1" }] }), sheet({ file_no: "0002", carried: 5 })];
    expect(carrySummary(withCarry, ["0001"])).toEqual({ carried: 2, lost: 1 });
    expect(carrySummary(withCarry, ["0001", "0002"])).toEqual({ carried: 7, lost: 1 });
  });

  it("登録の本文は、10桁の長さ + JSON + ブック(サーバーと同じ形)", async () => {
    const meta = { file_nos: ["0722", "0800"], sha256: "00".repeat(32), states: {} };
    const body = applyBody(meta, new Blob(["BOOK"]));
    const text = await body.text();
    const json = JSON.stringify(meta);
    expect(text.slice(0, 10)).toBe(String(new TextEncoder().encode(json).length).padStart(10, "0"));
    expect(text.slice(10)).toBe(`${json}BOOK`);
  });
});
