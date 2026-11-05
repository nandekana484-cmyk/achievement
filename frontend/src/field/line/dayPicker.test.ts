import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ja } from "../../i18n/ja";
import type { Board, BoardPlan } from "../../shared/api";
import { DayPicker } from "./DayPicker";
import { LineEventPanel } from "./LineEventPanel";
import { StepPanel } from "./StepPanel";
import { Timetable } from "./Timetable";
import { planBlockSub } from "./planMatch";

const t = (key: keyof typeof ja, vars?: Record<string, string | number>) => ja[key].replace(/\{(\w+)\}/g, (_, k: string) => String(vars?.[k] ?? ""));

const plan = (over: Partial<BoardPlan> = {}) =>
  ({
    plan: { kitting_no: "K1", run_no: 1, planned_qty: 100, takt_sec: null, lots: [], product_name: "基板A", status: "active", warnings: [], planned_start: "2026-11-05T09:00:00+09:00", planned_end: "2026-11-05T12:00:00+09:00" },
    events: [{ id: 1, seq: 1, step_type: "production", start_at: "2026-11-05T09:00:00+09:00", end_at: null, voided_at: null }],
    produced_qty: 40, ng_entries: [], completed: false, in_progress: true, progress: 0.5, closed: null,
    ...over,
  }) as unknown as BoardPlan;

const board = { date: "2026-11-05", today: "2026-11-05" };

describe("タイムテーブルの枠の「%」", () => {
  it("生産中の計画の枠に「%」を出さない(状態があるときは状態は出す)", () => {
    const flags = { selected: false, edge: false, overdue: false };
    expect(planBlockSub(plan(), flags, t)).not.toContain("%");
    expect(planBlockSub(plan({ completed: true }), flags, t)).toContain("完了");
    expect(planBlockSub(plan(), { ...flags, selected: true }, t)).toContain("選択中");
  });

  it("タイムテーブル全体にも「%」が出ない。右のパネルの進捗率は出る", () => {
    const b = {
      line_code: "S", ...board, workday_start: "2026-11-05T08:15:00+09:00", workday_end: "2026-11-06T08:15:00+09:00",
      display_start: "2026-11-04T20:15:00+09:00", display_end: "2026-11-06T20:15:00+09:00", plans: [plan()], line_events: [],
    } as unknown as Board;
    const tt = renderToStaticMarkup(createElement(Timetable, { board: b, nowMs: Date.parse("2026-11-05T10:00:00+09:00"), selectedKey: null, onSelect: () => undefined }));
    const text = tt.replace(/<[^>]*>/g, " "); // 画面に出る文字だけ(style の「%」は除く)
    expect(text).toContain("K1");
    expect(text).not.toContain("%");
    const panel = renderToStaticMarkup(createElement(StepPanel, { plan: plan(), isBusy: () => false, onStep: () => undefined, onNg: () => undefined, onRemark: () => undefined, onFix: () => undefined, onAdd: () => undefined, onHistory: () => undefined }));
    expect(panel).toContain("進捗率");
    expect(panel).toContain("50%");
  });
});

describe("表示する日の選択", () => {
  const picker = (b: { date: string; today: string } | null) => renderToStaticMarkup(createElement(DayPicker, { board: b, onChange: () => undefined }));

  it("今日のときは、日付の欄(今日の31日前〜14日後)があり、「表示のみ」の帯は無い。「今日」は押せない", () => {
    const html = picker(board);
    expect(html).toContain('value="2026-11-05"');
    expect(html).toContain('min="2026-10-05"');
    expect(html).toContain('max="2026-11-19"');
    expect(html).not.toContain("表示のみ");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>今日<\/button>/);
  });

  it("ほかの日のときは「表示のみ(今日ではありません)」の帯を出し、「今日」を押せる", () => {
    const html = picker({ date: "2026-11-03", today: "2026-11-05" });
    expect(html).toContain("表示のみ(今日ではありません)");
    expect(html).not.toMatch(/<button[^>]*disabled=""[^>]*>今日<\/button>/);
  });

  it("表示のみのとき、工程・NG・備考・追加・直すのボタンは押せない(識別票などへのリンクは actions に残る)", () => {
    const props = { plan: plan(), isBusy: () => false, onStep: () => undefined, onNg: () => undefined, onRemark: () => undefined, onFix: () => undefined, onAdd: () => undefined, onHistory: () => undefined };
    const live = renderToStaticMarkup(createElement(StepPanel, props));
    const ro = renderToStaticMarkup(createElement(StepPanel, { ...props, readOnly: true }));
    const disabled = (h: string) => (h.match(/<button[^>]*disabled=""/g) ?? []).length;
    // 工程6 + 直す6 + NG・備考・追加(履歴は読むだけ)
    expect(disabled(ro) - disabled(live)).toBeGreaterThanOrEqual(8);
    expect(ro).toMatch(/<button[^>]*disabled=""[^>]*class="[^"]*step-button|<button[^>]*class="[^"]*step-button[^"]*"[^>]*disabled=""/);
    const history = ro.match(/<button[^>]*>履歴|<button[^>]*>[^<]*訂正の履歴/);
    expect(history?.[0] ?? "").not.toContain("disabled");
  });

  it("表示のみのとき、付帯作業のボタンも押せない", () => {
    const reasons = [{ id: 1, name: "欠品", name_vi: null }] as never;
    const render = (readOnly: boolean) => renderToStaticMarkup(createElement(LineEventPanel, { reasons, openEvents: [], nowMs: 0, isBusy: () => false, onStart: () => undefined, onEnd: () => undefined, onFix: () => undefined, onHistory: () => undefined, readOnly }));
    expect(render(false)).not.toContain('disabled=""');
    expect(render(true)).toMatch(/<button[^>]*disabled=""[^>]*>欠品/);
  });
});
