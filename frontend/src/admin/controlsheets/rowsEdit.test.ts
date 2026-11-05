import { describe, expect, it } from "vitest";
import { addRow, blankRow, moveRow, PAGE_FIT_ROWS, removeRow, toPayload, tooManyRows, updateRow } from "./rowsEdit";

const named = (...names: string[]) => names.map((name) => ({ ...blankRow(), name }));
const names = (rows: { name: string }[]) => rows.map((r) => r.name);

describe("管理表の行の編集", () => {
  it("行を最後に足す、指定の行の下に足す", () => {
    expect(names(addRow(named("A", "B")))).toEqual(["A", "B", ""]);
    expect(names(addRow(named("A", "B"), 0))).toEqual(["A", "", "B"]);
    expect(blankRow()).toMatchObject({ kind: "none", use_line: true, link: "none", procedure: "" });
  });

  it("行を削除する", () => {
    expect(names(removeRow(named("A", "B", "C"), 1))).toEqual(["A", "C"]);
  });

  it("行を上下に動かす(端では動かない)", () => {
    expect(names(moveRow(named("A", "B", "C"), 2, -1))).toEqual(["A", "C", "B"]);
    expect(names(moveRow(named("A", "B", "C"), 0, 1))).toEqual(["B", "A", "C"]);
    const rows = named("A", "B");
    expect(moveRow(rows, 0, -1)).toBe(rows);
    expect(moveRow(rows, 1, 1)).toBe(rows);
  });

  it("行の項目を変える。ほかの行は変えない", () => {
    const rows = named("A", "B");
    const next = updateRow(rows, 1, { use_line: false, kind: "internal" });
    expect(next[1]).toMatchObject({ name: "B", use_line: false, kind: "internal" });
    expect(next[0]).toBe(rows[0]);
  });

  it("空の行(工程名も作業要領も空)を足せて、そのまま送れる。区分とライン名の欄の設定は空の行にも持てる", () => {
    const rows = updateRow(addRow(named("A")), 1, { kind: "internal", use_line: false });
    expect(rows[1]).toMatchObject({ name: "", procedure: "", kind: "internal", use_line: false });
    expect(toPayload(rows)[1]).toMatchObject({ name: "", name_vi: null, kind: "internal", use_line: false });
    expect(toPayload([{ ...blankRow(), name: " X線 ", name_vi: "  " }])[0]).toMatchObject({ name: "X線", name_vi: null });
  });

  it("20行を超えたら、1ページに収まらないことがあると警告する(20行まではしない)", () => {
    const rows = (n: number) => Array.from({ length: n }, blankRow);
    expect(PAGE_FIT_ROWS).toBe(20);
    expect(tooManyRows(rows(20))).toBe(false);
    expect(tooManyRows(rows(21))).toBe(true);
  });
});
