import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ControlSheet } from "./ControlSheet";
import { lotCounts, MAX_HEIGHT_PX, nextLevel, overflowsAtLimit, sheetRows } from "./controlSheetLayout";
import type { IdSlip } from "./idSlipLogic";

const row = (over = {}) => ({ name: "SMT-1", name_vi: null, kind: "internal" as const, procedure: "Side B", use_line: true, link: "none" as const, ...over });
const blank = (n: number, use_line = false) => Array.from({ length: n }, () => row({ name: "", kind: "none" as const, procedure: "", use_line })); // サーバーが足す空の行(登録した行に足す行は斜線 = use_line false。未登録の空の8行は斜線なし)
const slip = (cs: IdSlip["control_sheet"]): IdSlip => ({
  kitting_no: "0722-2-S-251014-02", line_code: "S", run_no: 2, file_no: "722", suf: "SUF-0722", product_name: "基板A",
  lots: [{ lot_no: "L001", order_qty: 1000, planned_qty: 300 }, { lot_no: "L002", order_qty: null, planned_qty: 50 }], lot_list: "L001, L002", control_sheet: cs,
});
const html = (s: IdSlip, lot = "L001") => renderToStaticMarkup(createElement(ControlSheet, { slip: s, lotNo: lot }));
const text = (h: string) => h.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");

describe("K社製品ロット管理票の欄", () => {
  it("未登録は、番号だけの空の8行(ライン名の欄は斜線なし)。管理No は空", () => {
    const rows = sheetRows({ registered: false, manager_no: "", rows: blank(8, true) });
    expect(rows.map((r) => r.no)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(rows.every((r) => r.name === "" && r.procedure === "" && r.useLine)).toBe(true);
  });

  it("登録した行は、番号を1から振る", () => {
    const rows = sheetRows({ registered: true, manager_no: "M", rows: [row(), row({ name: "X線検査", name_vi: "Kiểm tra X-quang", kind: "none" })] });
    expect(rows.map((r) => [r.no, r.name, r.nameVi])).toEqual([[1, "SMT-1", ""], [2, "X線検査", "Kiểm tra X-quang"]]);
  });

  it("当ロット数 A / C は、そのロットの生産数と発注数(発注数が無ければ空)", () => {
    const s = slip({ registered: false, manager_no: "", rows: blank(8) });
    expect(lotCounts(s, "L001")).toEqual({ a: "300", c: "1000" });
    expect(lotCounts(s, "L002")).toEqual({ a: "50", c: "" });
  });

  it("印刷の欄: ファイルNo.・管理No・製品名・ロットNo.・A / C・工程の行・組立工程へ", () => {
    const h = html(slip({ registered: true, manager_no: "MP-7", rows: [row(), row({ name: "X線検査", use_line: false, kind: "external", procedure: "検査数 5 枚" })] }));
    const t = text(h);
    for (const word of ["K社製品ロット管理票", "722", "MP-7", "基板A", "L001", "300", "1000", "SMT-1", "社内", "Nội bộ", "社外", "検査数 5 枚", "組立工程へ", "WHITE PAPER(A4)", "工程抜け確認印", "Số quản lý"]) expect(t).toContain(word);
    expect(t).not.toContain("PROCEDIMENTO"); // ポルトガル語は外した
  });

  it("ライン名の欄は、使わない行だけ斜線。作業要領の欄は罫線つき", () => {
    const h = html(slip({ registered: true, manager_no: "", rows: [row(), row({ use_line: false })] }));
    expect(h.match(/sk-diagonal/g)).toHaveLength(1);
    expect(h.match(/sk-proc sk-lined/g)).toHaveLength(2);
    expect(html(slip({ registered: false, manager_no: "", rows: blank(8, true) })).match(/sk-diagonal/g)).toBeNull(); // 未登録の空の8行は斜線なし
    expect(html(slip({ registered: true, manager_no: "", rows: [row(), ...blank(7)] })).match(/sk-diagonal/g)).toHaveLength(7); // 登録した行に足した行は斜線
    const mixed = html(slip({ registered: true, manager_no: "", rows: [row(), row({ name: "", procedure: "", use_line: true }), ...blank(6)] })); // 様式の例: 3の行だけライン名の欄を使う
    expect(mixed.match(/sk-diagonal/g)).toHaveLength(6);
    expect(mixed.match(/data-row=/g)).toHaveLength(8);
  });

  it("収まらないとき、次の詰め具合へ(最後の段階では止まる)", () => {
    expect(nextLevel(0, MAX_HEIGHT_PX)).toBeNull();
    expect(nextLevel(0, MAX_HEIGHT_PX + 1)).toBe(1);
    expect(nextLevel(7, 9999)).toBeNull();
    expect(overflowsAtLimit(7, MAX_HEIGHT_PX + 1)).toBe(true); // 一番詰めても収まらない
    expect(overflowsAtLimit(7, MAX_HEIGHT_PX)).toBe(false);
    expect(overflowsAtLimit(3, 9999)).toBe(false); // まだ詰められる
  });
});
