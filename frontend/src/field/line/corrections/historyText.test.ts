import { describe, expect, it } from "vitest";
import { makeTranslate } from "../../../i18n/translate";
import type { Correction } from "../../../shared/api";
import { changeLines, targetText } from "./historyText";

const t = makeTranslate("ja");
const base: Correction = {
  id: 1, target_table: "run_events", target_id: 10, kitting_no: "K1", line_code: "S", kind: "update", changes: [],
  reason: "mistake", reason_label: "押し間違い", note: null, corrected_by: 1, corrected_by_name: "山田",
  corrected_by_worker_id: "Y001", corrected_at: "2026-10-21T09:30:00+09:00", source: "field",
  step_type: "production", seq: 1, line_event_reason_name: null, line_event_reason_name_vi: null,
};
const change = (field: string, before: string | number | null, after: string | number | null, names = {}) =>
  ({ field, before, after, ...names });

describe("訂正の履歴の文", () => {
  it("変更は「項目: 前 → 後」。時刻は日本時間の月/日 時:分", () => {
    const c = { ...base, changes: [change("start_at", "2026-10-21T08:00:00+09:00", "2026-10-21T08:10:00+09:00"), change("produced_qty", 100, 120)] };
    expect(changeLines(c, t, "ja")).toEqual(["開始: 10/21 8:00 → 10/21 8:10", "生産数: 100 → 120"]);
    expect(targetText(c, t, "ja")).toBe("生産");
  });

  it("追加は後の値だけ。取り消しは項目を出さない", () => {
    const added = { ...base, kind: "add", changes: [change("step_type", null, "setup"), change("end_at", null, "2026-10-21T09:00:00+09:00")] };
    expect(changeLines(added, t, "ja")).toEqual(["工程: 段取り", "終了: 10/21 9:00"]);
    expect(changeLines({ ...base, kind: "void", changes: [change("voided_at", null, "2026-10-21T09:00:00+09:00")] }, t, "ja")).toEqual([]);
  });

  it("付帯作業の理由と設備は名前で出す(ベトナム語の名前があればそれ)。空は「なし」", () => {
    const c = {
      ...base, target_table: "line_events", step_type: null, line_event_reason_name: "マシントラブル", line_event_reason_name_vi: "Sự cố máy",
      changes: [change("reason_id", 1, 3, { before_name: "部品探し", after_name: "マシントラブル", after_name_vi: "Sự cố máy" }),
        change("equipment_id", null, 2, { after_name: "マウンター1" })],
    };
    expect(changeLines(c, t, "ja")).toEqual(["理由: 部品探し → マシントラブル", "設備: なし → マウンター1"]);
    expect(targetText(c, t, "vi")).toBe("Sự cố máy");
  });
});
