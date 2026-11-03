import { describe, expect, it } from "vitest";
import { makeTranslate } from "../../i18n/translate";
import { canSubmit, confirmLines, panelState, type SideLinkView, unlinkLines } from "./sideLink";

const t = makeTranslate("ja");
const view = (over: Partial<SideLinkView>): SideLinkView => ({
  role: "side2", partner: null, partner_source: null, decided_by: null, decided_at: null, suggested: null, candidates: [], ...over,
});

describe("panelState", () => {
  it("候補が1つなら、欄に最初から入れておく", () => {
    expect(panelState(view({ suggested: "K1", candidates: ["K1"] }))).toEqual({ mode: "input", initial: "K1", options: [], autoNote: false });
  });

  it("キー H でつながる面1は、欄に入れて自動のつなぎと分かるようにする", () => {
    expect(panelState(view({ suggested: "P1", partner_source: "h", candidates: ["P1", "P3"] }))).toEqual({
      mode: "input", initial: "P1", options: ["P1", "P3"], autoNote: true });
  });

  it("候補が複数で決まらないときは空欄にして、一覧から選べるようにする", () => {
    expect(panelState(view({ candidates: ["A", "B"] }))).toEqual({ mode: "input", initial: "", options: ["A", "B"], autoNote: false });
  });

  it("候補が無ければ空欄(一覧も出さない)", () => {
    expect(panelState(view({}))).toEqual({ mode: "input", initial: "", options: [], autoNote: false });
  });

  it("紐づけ済みなら相手を出す(直す・外す)。面1の画面は表示だけ", () => {
    expect(panelState(view({ partner: "K1", partner_source: "field", candidates: ["K1"] }))).toEqual({
      mode: "linked", partner: "K1", source: "field", options: ["K1"] });
    expect(panelState(view({ role: "side1", partner: "K2" }))).toEqual({ mode: "side1", partner: "K2" });
  });
});

describe("確認の文", () => {
  it("合わないロットの警告と、書き出し済みの確認を出す。どちらも無ければ確認なし", () => {
    expect(confirmLines({ mismatched_lots: [], exported: false }, t)).toEqual([]);
    expect(confirmLines({ mismatched_lots: ["L002(2回目だけ)"], exported: false }, t)).toHaveLength(1);
    const both = confirmLines({ mismatched_lots: ["L002(2回目だけ)", "L003(1回目だけ)"], exported: true }, t);
    expect(both[0]).toContain("L002(2回目だけ)、L003(1回目だけ)");
    expect(both[1]).toBe("書き出し済みです。既存アプリの値は管理者が直す必要があります");
  });

  it("外すときは、外す確認に、書き出し済みの注意を足す", () => {
    expect(unlinkLines(false, t)).toHaveLength(1);
    expect(unlinkLines(true, t)[1]).toContain("書き出し済みです");
  });

  it("空の入力は保存できない", () => {
    expect(canSubmit("  ")).toBe(false);
    expect(canSubmit(" 0722-1-S-251014-01 ")).toBe(true);
  });
});
