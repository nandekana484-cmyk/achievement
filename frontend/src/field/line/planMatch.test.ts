import { describe, expect, it } from "vitest";
import { makeTranslate } from "../../i18n/translate";
import type { BoardPlan, Plan, RunEvent } from "../../shared/api";
import { exactKittingMatch, foldForMatch, canClosePlan, isOutsideDisplay, isOverdueUnstarted, outsideMessage, planSummary } from "./planMatch";

const t = makeTranslate("ja");

const plan = (kitting_no: string, lot_no = "L1", start: string | null = "2026-10-21T09:00:00+09:00", end: string | null = "2026-10-21T12:00:00+09:00"): Plan => ({
  kitting_no, file_no: "0722", line_code: "S", product_name: "基板", run_no: 1, planned_qty: 100,
  planned_start: start, planned_end: end, deadline: null, issue_date: "2026-10-14", issue_seq: 1, status: "active", cancel_reason: null, is_stale: false,
  takt_sec: null, source_db: null, lots: [{ lot_no, product_name: "基板", planned_qty: 100 }], warnings: [],
});

describe("exactKittingMatch", () => {
  it("キッティングNo.が完全に一致する1件を返す(大文字・小文字、全角・半角、前後の空白は無視)", () => {
    const results = [plan("0722-1-S-251018-01"), plan("0722-1-S-251018-011")];
    expect(exactKittingMatch(results, "0722-1-S-251018-01")?.kitting_no).toBe("0722-1-S-251018-01");
    expect(exactKittingMatch(results, " ０７２２－１－ｓ－２５１０１８－０１ ")?.kitting_no).toBe("0722-1-S-251018-01");
  });

  it("一部一致だけ・一致が2件(ロット違い)なら選ばない", () => {
    expect(exactKittingMatch([plan("0722-1-S-251018-01")], "0722-1-S")).toBeNull();
    expect(exactKittingMatch([plan("0722-1-S-251018-01", "L1"), plan("0722-1-S-251018-01", "L2")], "0722-1-S-251018-01")).toBeNull();
    expect(exactKittingMatch([], "0722")).toBeNull();
  });

  it("比べるための形", () => {
    expect(foldForMatch(" ｔ４５８ ")).toBe("T458");
  });
});

describe("表示範囲の外", () => {
  const board = { display_start: "2026-10-20T20:15:00+09:00", display_end: "2026-10-22T20:15:00+09:00" };

  it("表示範囲と重なるかで判定する。日程が空なら外", () => {
    expect(isOutsideDisplay(plan("A"), board)).toBe(false);
    expect(isOutsideDisplay(plan("A", "L1", "2026-10-18T09:00:00+09:00", "2026-10-18T12:00:00+09:00"), board)).toBe(true);
    expect(isOutsideDisplay(plan("A", "L1", "2026-10-20T18:00:00+09:00", "2026-10-20T20:15:00+09:00"), board)).toBe(true);
    expect(isOutsideDisplay(plan("A", "L1", "2026-10-20T18:00:00+09:00", "2026-10-20T21:00:00+09:00"), board)).toBe(false);
    expect(isOutsideDisplay(plan("A", "L1", null, null), board)).toBe(true);
  });

  it("表示範囲外の文", () => {
    expect(outsideMessage(plan("A", "L1", "2026-10-18T09:00:00+09:00"), t)).toBe("表示範囲外の計画です(計画: 10/18 9:00〜)");
    expect(outsideMessage(plan("A", "L1", null, null), t)).toBe("表示範囲外の計画です(計画: 日程なし)");
  });
});

describe("計画の短い説明", () => {
  it("ロットが1つなら基板名、複数ならロットの数", () => {
    expect(planSummary(plan("A"), t)).toBe("基板・計画数 100・1回目");
    const multi = { ...plan("A"), planned_qty: 300, lots: [1, 2, 3].map((i) => ({ lot_no: `L${i}`, product_name: "基板", planned_qty: 100 })) };
    expect(planSummary(multi, t)).toBe("3ロット・計画数 300・1回目");
  });
});

describe("計画終了を過ぎた未着手", () => {
  const nowMs = Date.parse("2026-10-21T13:00:00+09:00");
  const ev = (voided: boolean) => ({ id: 1, voided_at: voided ? "2026-10-21T10:00:00+09:00" : null }) as unknown as RunEvent;
  const board = (events: RunEvent[], completed = false, end: string | null = "2026-10-21T12:00:00+09:00"): BoardPlan =>
    ({ plan: plan("A", "L1", "2026-10-21T09:00:00+09:00", end), events, completed }) as unknown as BoardPlan;

  it("計画終了を過ぎ、有効な記録が無く、完了でもなければ未着手の枠", () => {
    expect(isOverdueUnstarted(board([]), nowMs)).toBe(true);
    expect(isOverdueUnstarted(board([ev(true)]), nowMs)).toBe(true); // 取り消した記録だけ
  });

  it("計画終了の前、始めている、完了、日程なしは未着手の枠にしない", () => {
    expect(isOverdueUnstarted(board([], false, "2026-10-21T14:00:00+09:00"), nowMs)).toBe(false);
    expect(isOverdueUnstarted(board([ev(false)]), nowMs)).toBe(false);
    expect(isOverdueUnstarted(board([], true), nowMs)).toBe(false);
    expect(isOverdueUnstarted(board([], false, null), nowMs)).toBe(false);
  });
});

describe("計画終了のボタンと「終了(手動)」", () => {
  const nowMs = Date.parse("2026-10-21T13:00:00+09:00");
  const ev = (voided: boolean) => ({ id: 1, voided_at: voided ? "2026-10-21T10:00:00+09:00" : null }) as unknown as RunEvent;
  const bp = (over: Partial<BoardPlan> & { status?: string }, events: RunEvent[] = []): BoardPlan =>
    ({ plan: { ...plan("A"), status: over.status ?? "active" }, events, completed: false, closed: null, ...over }) as unknown as BoardPlan;
  const closed = { reason: "plan_change", note: null, closed_by_name: "鈴木", closed_at: "2026-10-21T12:00:00+09:00" };

  it("ボタンは、始まっていない(取り消した記録だけも含む)計画にだけ出る", () => {
    expect(canClosePlan(bp({}))).toBe(true);
    expect(canClosePlan(bp({}, [ev(true)]))).toBe(true);
    expect(canClosePlan(bp({}, [ev(false)]))).toBe(false); // 始まっている
  });

  it("取り消された計画・完了・すでに計画終了した計画には出さない", () => {
    expect(canClosePlan(bp({ status: "cancelled" }))).toBe(false);
    expect(canClosePlan(bp({ completed: true }))).toBe(false);
    expect(canClosePlan(bp({ closed }))).toBe(false);
  });

  it("計画終了した計画は、未着手(斜線)の見た目にしない", () => {
    expect(isOverdueUnstarted(bp({}), nowMs)).toBe(true);
    expect(isOverdueUnstarted(bp({ closed }), nowMs)).toBe(false);
  });
});
