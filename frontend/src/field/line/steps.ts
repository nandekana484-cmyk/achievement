// 工程の並び・名前・色と、工程の状態の判定(開発指針 5.4)。
import type { MessageKey } from "../../i18n/ja";
import type { Translate } from "../../i18n/translate";
import type { RunEvent, StepType } from "../../shared/api";
import { formatHM } from "./timeScale";

export const STEP_ORDER: StepType[] = ["setup", "n1_check", "production", "first_article", "xray", "cleanup"];

export const STEP_LABEL_KEYS: Record<StepType, MessageKey> = {
  setup: "step.setup",
  n1_check: "step.n1_check",
  production: "step.production",
  first_article: "step.first_article",
  xray: "step.xray",
  cleanup: "step.cleanup",
};

// 色だけで区別しないよう、表示では必ず工程名も出す
export const STEP_COLORS: Record<StepType, string> = {
  setup: "#8250df",
  n1_check: "#0969da",
  production: "#1a7f37",
  first_article: "#bf8700",
  xray: "#cf222e",
  cleanup: "#57606a",
};

export type StepState = "todo" | "doing" | "done";

export const STATE_KEYS: Record<StepState, MessageKey> = { todo: "stepState.todo", doing: "stepState.doing", done: "stepState.done" };

export type StepStatus = {
  step: StepType;
  state: StepState;
  label: string; // 生産は「生産 1回目」のように区切りの番号を付ける
  timeText: string;
  open: RunEvent | null; // 終了していない記録
  records: RunEvent[]; // その工程の記録(取り消したものを除く。開始の順)
  nextNumber: number; // 次に開始したときの区切りの番号(何回目か)
  action: "start" | "end";
  needsQty: boolean; // 生産の終了: 生産数を入れる
  needsReason: boolean; // 生産の2回目以降の開始: 再開理由を選ぶ
  needsConfirm: boolean; // 片付けの終了: 完了になることを確認する
};

/** 取り消していない記録(生産数・進捗・タイムテーブル・工程の状態は、これだけで決める)。 */
export function activeEvents(events: RunEvent[]): RunEvent[] {
  return events.filter((e) => !e.voided_at);
}

const byStart = (a: RunEvent, b: RunEvent) => Date.parse(a.start_at) - Date.parse(b.start_at) || a.seq - b.seq;

/**
 * 記録ごとの「何回目か」。取り消していない記録を、工程ごとに開始の順で数える。
 * 番号(seq)は取り消した記録や後から足した記録でも振り直さないので、画面ではこの数を出す。
 */
export function recordNumbers(events: RunEvent[]): Map<number, number> {
  const numbers = new Map<number, number>();
  const counts = new Map<string, number>();
  for (const e of activeEvents(events).sort(byStart)) {
    const n = (counts.get(e.step_type) ?? 0) + 1;
    counts.set(e.step_type, n);
    numbers.set(e.id, n);
  }
  return numbers;
}

/** 記録の名前(「段取り」「生産 2回目」)。 */
export function recordLabel(e: RunEvent, numbers: Map<number, number>, t: Translate): string {
  const step = e.step_type as StepType;
  if (step !== "production") return t(STEP_LABEL_KEYS[step]);
  return t("step.productionSeq", { seq: numbers.get(e.id) ?? e.seq });
}

/** その計画の工程の記録から、工程の状態と、次に押したときの動きを決める。 */
export function stepStatus(events: RunEvent[], step: StepType, t: Translate): StepStatus {
  const records = activeEvents(events).filter((e) => e.step_type === step).sort(byStart);
  const open = records.find((e) => !e.end_at) ?? null;
  const last = records.length ? records[records.length - 1] : null;
  const nextNumber = records.length + 1;
  const state: StepState = open ? "doing" : last ? "done" : "todo";

  let timeText = "";
  if (open) timeText = t("step.timeOpen", { start: formatHM(open.start_at) });
  else if (last?.end_at) timeText = t("step.timeRange", { start: formatHM(last.start_at), end: formatHM(last.end_at) });

  const numberForLabel = open ? records.indexOf(open) + 1 : nextNumber;
  const label = step === "production" ? t("step.productionSeq", { seq: numberForLabel }) : t(STEP_LABEL_KEYS[step]);
  const action = open ? "end" : "start";
  return {
    step, state, label, timeText, open, records, nextNumber, action,
    needsQty: step === "production" && action === "end",
    needsReason: step === "production" && action === "start" && records.length >= 1,
    needsConfirm: step === "cleanup" && action === "end",
  };
}

/** 進捗率などの割合を「50%」の形にする。空なら「—」。 */
export function formatPercent(ratio: number | null | undefined): string {
  return ratio === null || ratio === undefined ? "—" : `${Math.round(ratio * 100)}%`;
}
