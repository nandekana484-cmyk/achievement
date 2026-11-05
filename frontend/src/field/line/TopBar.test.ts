import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Board, BoardPlan } from "../../shared/api";
import { SideLinkButton, SideLinkNote } from "./SideLinkPanel";
import { TopBar } from "./TopBar";

const board = (efficiency: number | null, progress: number | null) =>
  ({
    efficiency: { efficiency, excluded: 0 }, current_operator: null,
    plans: [{ plan: { kitting_no: "K1" }, in_progress: true, progress }],
  }) as unknown as Board;

const top = (b: Board | null) =>
  renderToStaticMarkup(createElement(MemoryRouter, null, createElement(TopBar, { lineCode: "S", lineName: "Sライン", board: b, onChangeOperator: () => undefined })));

describe("トップバー", () => {
  it("効率は出すが、進捗率は出さない(生産中の計画があっても)", () => {
    const html = top(board(0.8, 0.5));
    expect(html).toContain("効率");
    expect(html).toContain("80%");
    expect(html).not.toContain("進捗率");
    expect(html).not.toContain("50%");
    expect(html).not.toContain("K1");
  });

  it("効率が200%を超えたら「***%」(200%ちょうどまでは数)", () => {
    expect(top(board(2, null))).toContain("200%");
    expect(top(board(2.001, null))).toContain("***%");
    expect(top(board(2.5, null))).toContain("***%");
    expect(top(board(2.5, null))).not.toContain("250%");
  });
});

const plan = (side_link: Record<string, unknown> | null) => ({ plan: { kitting_no: "0722-2-S-261014-02" }, side_link }) as unknown as BoardPlan;
const render = (node: ReturnType<typeof createElement>) => renderToStaticMarkup(createElement(MemoryRouter, null, node));

describe("紐づけのボタン", () => {
  it("2回目の計画: 紐づけのページへのリンクに、今の状態(未紐づけ / 紐づけ済み)を出す", () => {
    const unlinked = render(createElement(SideLinkButton, { plan: plan({ role: "side2", partner: null }) }));
    expect(unlinked).toContain('href="/field/link/0722-2-S-261014-02"');
    expect(unlinked).toContain("紐づけ");
    expect(unlinked).toContain("未紐づけ");
    const linked = render(createElement(SideLinkButton, { plan: plan({ role: "side2", partner: "0722-1-S-261014-01" }) }));
    expect(linked).toContain("紐づけ済み");
    expect(linked).not.toContain("未紐づけ");
  });

  it("1回目の計画と、紐づけの情報が無い計画には、ボタンを出さない", () => {
    expect(render(createElement(SideLinkButton, { plan: plan({ role: "side1", partner: "X" }) }))).toBe("");
    expect(render(createElement(SideLinkButton, { plan: plan(null) }))).toBe("");
  });

  it("1回目の計画には、紐づいた2回目を表示するだけ", () => {
    expect(render(createElement(SideLinkNote, { plan: plan({ role: "side1", partner: "0722-2-S-261014-02" }) }))).toContain("紐づいた2回目: 0722-2-S-261014-02");
    expect(render(createElement(SideLinkNote, { plan: plan({ role: "side1", partner: null }) }))).toBe("");
    expect(render(createElement(SideLinkNote, { plan: plan({ role: "side2", partner: "X" }) }))).toBe("");
  });
});
