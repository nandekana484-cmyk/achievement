// 訂正の履歴の1件を、画面に出す文にする(画面から切り離して vitest でテストする)。
import type { MessageKey } from "../../../i18n/ja";
import { type Lang, localName, type Translate } from "../../../i18n/translate";
import type { Correction, CorrectionChange, StepType } from "../../../shared/api";
import { STEP_LABEL_KEYS } from "../steps";
import { formatMDHM } from "../timeScale";

const FIELD_KEYS: Record<string, MessageKey> = {
  start_at: "history.field.start_at",
  end_at: "history.field.end_at",
  produced_qty: "history.field.produced_qty",
  reason_id: "history.field.reason_id",
  equipment_id: "history.field.equipment_id",
  reason_text: "history.field.reason_text",
  step_type: "history.field.step_type",
};

export const KIND_KEYS: Record<string, MessageKey> = {
  update: "history.kind.update",
  void: "history.kind.void",
  add: "history.kind.add",
};

export const SOURCE_KEYS: Record<string, MessageKey> = { field: "history.source.field", admin: "history.source.admin" };

function valueText(c: CorrectionChange, side: "before" | "after", t: Translate, lang: Lang): string {
  const v = c[side];
  if (v === null || v === undefined || v === "") return t("history.empty");
  if (c.field === "start_at" || c.field === "end_at") return formatMDHM(String(v));
  if (c.field === "step_type") return t(STEP_LABEL_KEYS[v as StepType]);
  if (c.field === "reason_id" || c.field === "equipment_id") {
    const name = side === "before" ? c.before_name : c.after_name;
    const nameVi = side === "before" ? c.before_name_vi : c.after_name_vi;
    return name ? localName(lang, name, nameVi) : String(v);
  }
  return String(v);
}

/** 変わった項目ごとの文(「開始: 10/21 8:00 → 10/21 8:10」)。取り消しは項目を出さない。 */
export function changeLines(c: Correction, t: Translate, lang: Lang): string[] {
  if (c.kind === "void") return [];
  return c.changes.filter((x) => FIELD_KEYS[x.field]).map((x) => {
    const field = t(FIELD_KEYS[x.field]);
    const after = valueText(x, "after", t, lang);
    return c.kind === "add" ? t("history.added", { field, after }) : t("history.change", { field, before: valueText(x, "before", t, lang), after });
  });
}

/** 何を直したか(工程の名前か、付帯作業の理由の名前)。 */
export function targetText(c: Correction, t: Translate, lang: Lang): string {
  if (c.step_type) return t(STEP_LABEL_KEYS[c.step_type as StepType]);
  return c.line_event_reason_name ? localName(lang, c.line_event_reason_name, c.line_event_reason_name_vi) : "";
}
