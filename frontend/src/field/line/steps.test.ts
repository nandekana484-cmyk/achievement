import { describe, expect, it } from "vitest";
import { makeTranslate } from "../../i18n/translate";
import type { RunEvent } from "../../shared/api";
import { formatPercent, recordLabel, recordNumbers, stepStatus } from "./steps";

const t = makeTranslate("ja");
let nextId = 1;
const ev = (step: string, seq: number, start: string, end: string | null): RunEvent => ({
  id: nextId++, kitting_no: "K1", step_type: step, seq,
  start_at: `2026-10-21T${start}:00+09:00`, end_at: end ? `2026-10-21T${end}:00+09:00` : null,
  started_by: 1, started_by_name: "山田", ended_by: end ? 1 : null, ended_by_name: end ? "山田" : null,
  produced_qty: null, restart_reason_id: null, restart_reason_name: null, equipment_id: null, equipment_name: null, added_later: false,
});

describe("stepStatus", () => {
  it("記録が無ければ未着手で、押すと開始", () => {
    const s = stepStatus([], "setup", t);
    expect(s).toMatchObject({ state: "todo", label: "段取り", action: "start", timeText: "", needsQty: false, needsReason: false });
  });

  it("終了していない記録があれば作業中で、押すと終了", () => {
    const s = stepStatus([ev("setup", 1, "08:00", null)], "setup", t);
    expect(s).toMatchObject({ state: "doing", action: "end", timeText: "08:00 〜" });
  });

  it("終了していれば済。押すと、もう一度開始(やり直し)", () => {
    const s = stepStatus([ev("setup", 1, "08:00", "08:20")], "setup", t);
    expect(s).toMatchObject({ state: "done", action: "start", timeText: "08:00 〜 08:20", nextNumber: 2 });
  });

  it("ほかの工程の記録は関係しない", () => {
    expect(stepStatus([ev("production", 1, "08:00", null)], "setup", t).state).toBe("todo");
  });

  it("生産は区切りの番号を出し、終了では生産数を入れる", () => {
    expect(stepStatus([], "production", t)).toMatchObject({ label: "生産 1回目", needsReason: false });
    const doing = stepStatus([ev("production", 1, "08:00", null)], "production", t);
    expect(doing).toMatchObject({ label: "生産 1回目", action: "end", needsQty: true });
  });

  it("生産の2回目以降の開始では再開理由を選ぶ", () => {
    const s = stepStatus([ev("production", 1, "08:00", "09:00"), ev("production", 2, "09:10", "10:00")], "production", t);
    expect(s).toMatchObject({ label: "生産 3回目", action: "start", needsReason: true, nextNumber: 3 });
  });

  it("取り消した記録は数えない(取り消した生産だけなら、次は1回目で再開理由は要らない)", () => {
    const voided = { ...ev("production", 1, "08:00", null), voided_at: "2026-10-21T08:05:00+09:00" };
    expect(stepStatus([voided], "production", t)).toMatchObject({ state: "todo", label: "生産 1回目", needsReason: false, records: [] });
  });

  it("後から足した記録も開始の順に並べる(番号は振り直さない)", () => {
    const later = ev("production", 3, "07:00", "07:30"); // 後から足した、いちばん早い区切り
    const events = [ev("production", 1, "08:00", "09:00"), ev("production", 2, "09:10", null), later];
    const s = stepStatus(events, "production", t);
    expect(s).toMatchObject({ label: "生産 3回目", action: "end", nextNumber: 4 });
    expect(recordLabel(later, recordNumbers(events), t)).toBe("生産 1回目");
  });

  it("片付けの終了では確認する", () => {
    expect(stepStatus([ev("cleanup", 1, "16:00", null)], "cleanup", t)).toMatchObject({ action: "end", needsConfirm: true });
    expect(stepStatus([], "cleanup", t).needsConfirm).toBe(false);
  });
});

describe("formatPercent", () => {
  it("割合を%にする。空は「—」", () => {
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(0.3333)).toBe("33%");
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(undefined)).toBe("—");
  });
});
